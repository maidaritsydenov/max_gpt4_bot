import yaml
import dotenv
from pathlib import Path

config_dir = Path(__file__).parent.parent.resolve() / "config"

# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# load .env config
config_env = dotenv.dotenv_values(config_dir / "config.env")

# config parameters
telegram_token = config_yaml["telegram_token"]
openai_api_key = config_yaml["openai_api_key"]
payment_token = config_yaml["payment_token"]
bot_username = config_yaml["bot_username"]

SBER_SALUTE_TOKEN = config_yaml['SBER_SALUTE_TOKEN']
SBER_SALUTE_SCOPE = config_yaml['SBER_SALUTE_SCOPE']
PATH_TO_SERT_LINUX = config_yaml['PATH_TO_SERT_LINUX']
# PATH_TO_SERT_WINDOWS = config_yaml['PATH_TO_SERT_WINDOWS']

use_chatgpt_api = config_yaml.get("use_chatgpt_api", True)
admin_ids = config_yaml['admin_ids']
allowed_telegram_usernames = config_yaml["allowed_telegram_usernames"]
new_dialog_timeout = config_yaml["new_dialog_timeout"]
token_limit_for_users = config_yaml["token_limit_for_users"]
update_token_limit = config_yaml["update_token_limit"]
enable_message_streaming = config_yaml.get("enable_message_streaming", True)
mongodb_uri = f"mongodb://mongo:{config_env['MONGODB_PORT']}"

# chat_modes
with open(config_dir / "chat_modes.yml", 'r') as f:
    chat_modes = yaml.safe_load(f)

# prices_package  
with open(config_dir / "prices.yml", 'r') as f:
    prices_package = yaml.safe_load(f)

# prices
chatgpt_price_per_1000_tokens = config_yaml.get("chatgpt_price_per_1000_tokens", 0.002)
gpt_price_per_1000_tokens = config_yaml.get("gpt_price_per_1000_tokens", 0.02)
whisper_price_per_1_min = config_yaml.get("whisper_price_per_1_min", 0.006)
dalle_price_per_one_image = config_yaml.get("dalle_price_per_one_image", 0.020)

# code phrases
CHATGPT_GROUP = config_yaml.get("CHATGPT_GROUP")
DALLE_GROUP = config_yaml.get("DALLE_GROUP")
DALLE_PRIVATE = config_yaml.get("DALLE_PRIVATE")
SALUTESPEECH_GROUP = config_yaml.get("SALUTESPEECH_GROUP")
SALUTESPEECH_PRIVATE = config_yaml.get("SALUTESPEECH_PRIVATE")