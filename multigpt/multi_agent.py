import random

from autogpt.agent import Agent
from multigpt import discord_utils


class MultiAgent(Agent):

    def __init__(
            self,
            ai_name,
            memory,
            full_message_history,
            prompt,
            user_input,
            agent_id
    ):
        super().__init__(
            ai_name=ai_name,
            memory=memory,
            full_message_history=full_message_history,
            next_action_count=0,
            prompt=prompt,
            user_input=user_input,
        )
        self.agent_id = agent_id
        self.auditory_buffer = []  # contains the non processed parts of the conversation
        self.avatar_url_base = 'https://discord-emojis.s3.eu-central-1.amazonaws.com/musk'
        self.avatar_url = "https://discord-emojis.s3.eu-central-1.amazonaws.com/musk_neutral_1.png"
        self.webhook_url = 'https://discord.com/api/webhooks/1100404997981749278/TXufpBkW4VsUA-WWEj91ayjTb3WUI7J0I-9IKmu7XLTgoyuQnQgUVbkAEtmk2B_OoyBs'

    def receive_message(self, speaker, message):
        self.auditory_buffer.append((speaker.ai_name, message))

    def set_emotional_state(self, emotion: str):
        emotional_states = ["agreement", "critique", "surprise", "annoyance", "neutral", "amusement", "idea", "sad"]
        if emotion in emotional_states:
            self.avatar_url = f"{self.avatar_url_base}_{emotion}_{random.randint(1, 2)}.png"
        else:
            self.avatar_url = "https://discord-emojis.s3.eu-central-1.amazonaws.com/musk_neutral_1.png"

    def send_message_discord(self, message):
        discord_utils.send_message(message, self.ai_name, self.webhook_url, self.avatar_url)
