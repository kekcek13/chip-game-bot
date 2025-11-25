import logging
import random
import os
from typing import List, Dict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка токена из переменных окружения Railway
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'ВАШ_ТОКЕН_ОТ_BOTFATHER')

if BOT_TOKEN == 'ВАШ_ТОКЕН_ОТ_BOTFATHER':
    print("❌ ОШИБКА: Токен бота не настроен!")
    print("Добавьте BOT_TOKEN в переменные окружения Railway")
    exit(1)

# Хранилище игр
active_games = {}

class ChipGame:
    def __init__(self):
        self.suits = ['♣', '♦', '♥', '♠']
        self.ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.suit_values = {suit: i for i, suit in enumerate(self.suits)}
        self.rank_values = {rank: i for i, rank in enumerate(self.ranks)}
        
        self.players = {}
        self.deck = []
        self.discard_pile = []
        self.turn_order = []
        self.current_player_index = 0
        self.attack_cards = []
        self.defend_cards = []
        self.game_state = "waiting"
        self.winners = []
        
    def create_deck(self) -> List[str]:
        deck = [f'{rank}{suit}' for suit in self.suits for rank in self.ranks]
        random.shuffle(deck)
        return deck
    
    def add_player(self, player_id: str, player_name: str):
        self.players[player_id] = {
            'name': player_name,
            'cards': [],
            'status': 'active'
        }
    
    def start_game(self):
        if len(self.players) < 2:
            return "❌ Недостаточно игроков. Нужно минимум 2 игрока"
            
        self.deck = self.create_deck()
        self.discard_pile = []
        self.game_state = "playing"
        self.winners = []
        
        for player_id in self.players:
            self.players[player_id]['cards'] = []
            for _ in range(3):
                if self.deck:
                    self.players[player_id]['cards'].append(self.deck.pop())
            self.players[player_id]['status'] = 'active'
        
        for player_id, player_data in self.players.items():
            if self.check_chip_victory(player_data['cards']):
                self.players[player_id]['status'] = 'winner'
                self.winners.append(player_id)
                return f"🎉 {player_data['name']} сразу собрал ЧИП и побеждает!"
        
        self.turn_order = list(self.players.keys())
        self.determine_first_player()
        
        return "🎮 Игра началась! Используйте /state чтобы увидеть состояние игры"
    
    def determine_first_player(self):
        first_player = None
        lowest_card_value = float('inf')
        
        for player_id in self.players:
            if self.players[player_id]['status'] != 'active':
                continue
                
            for card in self.players[player_id]['cards']:
                card_value = self.get_card_value(card)
                if card_value < lowest_card_value:
                    lowest_card_value = card_value
                    first_player = player_id
        
        if first_player in self.turn_order:
            index = self.turn_order.index(first_player)
            self.turn_order = self.turn_order[index:] + self.turn_order[:index]
        
        self.current_player_index = 0
    
    def get_card_value(self, card: str) -> int:
        rank = card[:-1]
        suit = card[-1]
        return self.rank_values[rank] * 10 + self.suit_values[suit]
    
    def get_card_suit(self, card: str) -> str:
        return card[-1]
    
    def get_card_rank(self, card: str) -> str:
        return card[:-1]
    
    def check_chip_victory(self, cards: List[str]) -> bool:
        suit_count = {}
        for card in cards:
            suit = self.get_card_suit(card)
            suit_count[suit] = suit_count.get(suit, 0) + 1
            if suit_count[suit] >= 3:
                return True
        return False
    
    def get_current_player(self) -> str:
        return self.turn_order[self.current_player_index]
    
    def get_next_player(self) -> str:
        next_index = (self.current_player_index + 1) % len(self.turn_order)
        return self.turn_order[next_index]
    
    def attack(self, player_id: str, card: str) -> str:
        if self.game_state != "playing":
            return "❌ Игра не начата или завершена"
            
        if player_id != self.get_current_player():
            return "❌ Сейчас не ваш ход"
            
        if card not in self.players[player_id]['cards']:
            return "❌ У вас нет такой карты"
        
        defender_id = self.get_next_player()
        self.attack_cards = [card]
        self.defend_cards = []
        self.players[player_id]['cards'].remove(card)
        
        return f"⚔️ {self.players[player_id]['name']} атакует {self.players[defender_id]['name']} картой {card}"
    
    def defend(self, defender_id: str, defending_card: str) -> str:
        if self.game_state != "playing":
            return "❌ Игра не начата или завершена"
            
        current_defender = self.get_next_player()
        if defender_id != current_defender:
            return "❌ Сейчас не ваша очередь защищаться"
            
        if defending_card not in self.players[defender_id]['cards']:
            return "❌ У вас нет такой карты"
        
        attacking_card = self.attack_cards[len(self.defend_cards)]
        
        if (self.get_card_suit(defending_card) == self.get_card_suit(attacking_card) and 
            self.get_card_value(defending_card) > self.get_card_value(attacking_card)):
            
            self.defend_cards.append(defending_card)
            self.players[defender_id]['cards'].remove(defending_card)
            
            if len(self.defend_cards) == len(self.attack_cards):
                self.discard_pile.extend(self.attack_cards)
                self.discard_pile.extend(self.defend_cards)
                self.end_turn(successful_defense=True)
                return "✅ Успешная защита! Карты уходят в сброс."
            else:
                return f"✅ Отбито картой {defending_card}"
        else:
            return "❌ Нельзя отбиться этой картой - нужна карта той же масти, но старше"
    
    def take_cards(self, defender_id: str) -> str:
        if self.game_state != "playing":
            return "❌ Игра не начата или завершена"
            
        current_defender = self.get_next_player()
        if defender_id != current_defender:
            return "❌ Сейчас не ваша очередь защищаться"
        
        all_cards = self.attack_cards + self.defend_cards
        self.players[defender_id]['cards'].extend(all_cards)
        
        self.end_turn(successful_defense=False)
        return f"📥 {self.players[defender_id]['name']} забирает все карты"
    
    def end_turn(self, successful_defense: bool):
        self.attack_cards = []
        self.defend_cards = []
        self.draw_cards()
        self.check_victories()
        
        if successful_defense:
            self.current_player_index = (self.current_player_index + 1) % len(self.turn_order)
    
    def draw_cards(self):
        players_to_draw = [self.get_current_player(), self.get_next_player()]
        
        for player_id in players_to_draw:
            if self.players[player_id]['status'] != 'active':
                continue
                
            while len(self.players[player_id]['cards']) < 3:
                if not self.deck:
                    if self.discard_pile:
                        self.deck = self.discard_pile
                        random.shuffle(self.deck)
                        self.discard_pile = []
                    else:
                        break
                
                if self.deck:
                    self.players[player_id]['cards'].append(self.deck.pop())
    
    def check_victories(self):
        for player_id in self.players:
            if (self.players[player_id]['status'] == 'active' and 
                self.check_chip_victory(self.players[player_id]['cards'])):
                self.players[player_id]['status'] = 'winner'
                self.winners.append(player_id)
    
    def get_game_state(self) -> Dict:
        return {
            'players': {
                pid: {
                    'name': data['name'],
                    'cards': data['cards'],
                    'status': data['status']
                } for pid, data in self.players.items()
            },
            'current_player': self.get_current_player(),
            'defender': self.get_next_player(),
            'attack_cards': self.attack_cards,
            'defend_cards': self.defend_cards,
            'game_state': self.game_state,
            'winners': self.winners,
            'deck_count': len(self.deck),
            'discard_count': len(self.discard_pile)
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет {user.first_name}! 🎮\n"
        "Добро пожаловать в игру ЧИП!\n\n"
        "🎯 Основные команды:\n"
        "/create_game - Создать игру\n"
        "/join_game КОД - Присоединиться\n"
        "/start_game - Начать игру\n"
        "/state - Состояние игры\n\n"
        "🎮 Игровые команды:\n"
        "/attack КАРТА - Атаковать\n"
        "/defend КАРТА - Защититься\n"
        "/take - Взять карты\n\n"
        "❓ Помощь:\n"
        "/rules - Правила игры\n"
        "/help - Все команды"
    )

async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = ChipGame()
    game.add_player(str(user.id), user.first_name)
    active_games[str(user.id)] = game
    await update.message.reply_text(
        "🎮 Игра 'Чип' создана!\n\n"
        "📋 Другие игроки могут присоединиться:\n"
        f"/join_game {user.id}\n\n"
        "▶️ Когда все присоединятся, запустите:\n"
        "/start_game"
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажите код игры: /join_game КОД")
        return
        
    room_code = context.args[0]
    user = update.effective_user
    
    if room_code not in active_games:
        await update.message.reply_text("❌ Игра не найдена!")
        return
        
    game = active_games[room_code]
    
    if str(user.id) in game.players:
        await update.message.reply_text("❌ Вы уже в этой игре!")
        return
        
    game.add_player(str(user.id), user.first_name)
    player_names = [p['name'] for p in game.players.values()]
    await update.message.reply_text(
        f"✅ Вы присоединились к игре!\n\n"
        f"👥 Игроки: {', '.join(player_names)}\n\n"
        f"▶️ Создатель игры может запустить:\n"
        f"/start_game"
    )

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = active_games.get(str(user.id))
    
    if not game:
        await update.message.reply_text("❌ Сначала создайте игру: /create_game")
        return
        
    result = game.start_game()
    await update.message.reply_text(result)
    
    state = game.get_game_state()
    await send_game_state(update, state)

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = find_player_game(str(user.id))
            
    if not game:
        await update.message.reply_text("❌ Вы не в игре!")
        return
        
    if not context.args:
        await update.message.reply_text("❌ Укажите карту: /attack 7♠")
        return
        
    card = context.args[0]
    result = game.attack(str(user.id), card)
    await update.message.reply_text(result)
    
    state = game.get_game_state()
    await send_game_state(update, state)

async def defend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = find_player_game(str(user.id))
            
    if not game:
        await update.message.reply_text("❌ Вы не в игре!")
        return
        
    if not context.args:
        await update.message.reply_text("❌ Укажите карту для защиты: /defend 8♠")
        return
        
    card = context.args[0]
    result = game.defend(str(user.id), card)
    await update.message.reply_text(result)
    
    state = game.get_game_state()
    await send_game_state(update, state)

async def take_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = find_player_game(str(user.id))
            
    if not game:
        await update.message.reply_text("❌ Вы не в игре!")
        return
        
    result = game.take_cards(str(user.id))
    await update.message.reply_text(result)
    
    state = game.get_game_state()
    await send_game_state(update, state)

async def game_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game = find_player_game(str(user.id))
            
    if not game:
        await update.message.reply_text("❌ Вы не в игре!")
        return
        
    state = game.get_game_state()
    await send_game_state(update, state)

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Правила игры ЧИП:\n\n"
        "🎯 Цель: собрать 3 карты одной масти\n\n"
        "🃏 Ход игры:\n"
        "• Игроки ходят по очереди на следующего игрока\n"
        "• Атакующий кидает карту\n"
        "• Защищающийся должен отбиться картой той же масти, но старше\n"
        "• Если не может отбиться - забирает все карты\n"
        "• Если отбился - карты уходят в сброс\n\n"
        "🏆 Победа:\n"
        "• Первый игрок с 3 картами одной масти побеждает\n"
        "• Можно выиграть сразу при раздаче (счастливчик!)\n\n"
        "♣️ ♦️ ♥️ ♠️ Приоритет мастей:\n"
        "Крести < Бубны < Червы < Пики"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 Помощь по командам:\n\n"
        "🎯 Основные:\n"
        "/start - Начать работу\n"
        "/create_game - Создать игру\n"
        "/join_game КОД - Присоединиться\n"
        "/start_game - Начать игру\n"
        "/state - Состояние игры\n\n"
        "🎮 Игровые:\n"
        "/attack КАРТА - Атаковать (пример: /attack 7♠)\n"
        "/defend КАРТА - Защититься\n"
        "/take - Взять карты\n\n"
        "❓ Информация:\n"
        "/rules - Правила игры\n"
        "/help - Эта справка"
    )

def find_player_game(player_id: str):
    for game in active_games.values():
        if player_id in game.players:
            return game
    return None

async def send_game_state(update, state):
    text = "🎮 Состояние игры:\n\n"
    
    current_player = state['current_player']
    defender = state['defender']
    
    if current_player in state['players']:
        text += f"🎯 Текущий ход: {state['players'][current_player]['name']}\n"
    if defender in state['players']:
        text += f"🛡️ Защищается: {state['players'][defender]['name']}\n"
    
    if state['attack_cards']:
        text += f"⚔️ Карты атаки: {', '.join(state['attack_cards'])}\n"
    if state['defend_cards']:
        text += f"🛡️ Карты защиты: {', '.join(state['defend_cards'])}\n"
    
    text += "\n👥 Игроки:\n"
    for player_id, player_data in state['players'].items():
        status_icon = "🏆" if player_data['status'] == 'winner' else "🎮"
        text += f"{status_icon} {player_data['name']}: {len(player_data['cards'])} карт\n"
        if player_id == str(update.effective_user.id):
            text += f"   📋 Ваши карты: {', '.join(player_data['cards'])}\n"
    
    text += f"\n📊 Карт в колоде: {state['deck_count']}"
    text += f"\n🗑️ Карт в сбросе: {state['discard_count']}"
    
    if state['winners']:
        text += "\n\n🎉 🏆 ПОБЕДИТЕЛИ: 🏆\n"
        winners_names = [state['players'][wid]['name'] for wid in state['winners']]
        text += ", ".join(winners_names)
        text += "\n\n🎊 Игра завершена!"
    
    await update.message.reply_text(text)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("create_game", create_game))
    application.add_handler(CommandHandler("join_game", join_game))
    application.add_handler(CommandHandler("start_game", start_game))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("defend", defend))
    application.add_handler(CommandHandler("take", take_cards))
    application.add_handler(CommandHandler("state", game_state))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("help", help_command))
    
    print("🤖 Бот запущен на Railway...")
    print("🟢 Теперь можете писать боту в Telegram!")
    application.run_polling()

if __name__ == "__main__":
    main()

