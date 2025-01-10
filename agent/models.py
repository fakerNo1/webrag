from copy import deepcopy
from dotenv import load_dotenv
from lagent.llms import (
    GPTAPI
)

# openai_api_base needs to fill in the complete chat api address, such as: https://api.openai.com/v1/chat/completions
gpt4 = dict(
    type=GPTAPI,
    model_type="gpt-4-turbo",
    key='sk-SWy7iReuR8pGAZyeuRa75YSocok8BNxcCFkWByIV8AdskdRY',
    api_base='https://api2.aigcbest.top/v1/chat/completions',
)


