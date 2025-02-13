import os
import sys
from datetime import datetime

from lagent.actions import WebBrowser
from lagent.agents.stream import get_plugin_prompt
from lagent.llms import INTERNLM2_META, LMDeployServer,GPTAPI
from lagent.prompts import InterpreterParser, PluginParser

from agent.mindsearch_agent import MindSearchAgent
from agent.mindsearch_prompt import (
    FINAL_RESPONSE_CN,
    GRAPH_PROMPT_CN,
    searcher_context_template_cn,
    searcher_input_template_cn,
    searcher_system_prompt_cn,
    graph_fewshot_example_cn
)


lang = "cn"
date = datetime.now().strftime("The current date is %Y-%m-%d.")

llm = GPTAPI(
    model_type="gpt-4-turbo",
    key='sk-SWy7iReuR8pGAZyeuRa75YSocok8BNxcCFkWByIV8AdskdRY',
    api_base='https://api2.aigcbest.top/v1/chat/completions',
)

plugins = [WebBrowser(searcher_type="BingSearch", topk=6,api_key="430135bcd8944d66a22f3e92d5a5d0d7")]

searcher_cfg=dict(
    llm=llm,
    plugins=plugins,
    template=date,
    output_format=PluginParser(
        template=searcher_system_prompt_cn,
        tool_info=get_plugin_prompt(plugins),
    ),
    user_input_template=searcher_input_template_cn,
    user_context_template=searcher_context_template_cn
)


agent = MindSearchAgent(
    llm=llm,
    template=date,
    output_format=InterpreterParser(template=GRAPH_PROMPT_CN+graph_fewshot_example_cn),
    searcher_cfg=searcher_cfg,
    summary_prompt=FINAL_RESPONSE_CN,
    max_turn=10,
)


for agent_return in agent("王者荣耀本赛季最强射手"):
    pass

print("-----------------------end output!!!-----------------------")
print(agent_return.sender)
print(agent_return.content)
print(agent_return.formatted["ref2url"])


# import os
# import sys
# from datetime import datetime

# from lagent.actions import WebBrowser
# from lagent.agents.stream import get_plugin_prompt
# from lagent.llms import INTERNLM2_META, LMDeployServer
# from lagent.prompts import InterpreterParser, PluginParser

# from agent.mindsearch_agent import MindSearchAgent
# from agent.mindsearch_prompt import (
#     FINAL_RESPONSE_CN,
#     GRAPH_PROMPT_CN,
#     searcher_context_template_cn,
#     searcher_input_template_cn,
#     searcher_system_prompt_cn
# )

# lang = "cn"
# date = datetime.now().strftime("The current date is %Y-%m-%d.")
# llm = LMDeployServer(
#     path="internlm/internlm2_5-7b-chat",
#     model_name="internlm2",
#     meta_template=INTERNLM2_META,
#     top_p=0.8,
#     top_k=1,
#     temperature=1.0,
#     max_new_tokens=8192,
#     repetition_penalty=1.02,
#     stop_words=["<|im_end|>", "<|action_end|>"],
# )
# plugins = [WebBrowser(searcher_type="BingSearch", topk=6,api_key="430135bcd8944d66a22f3e92d5a5d0d7")]
# agent = MindSearchAgent(
#     llm=llm,
#     template=date,
#     output_format=InterpreterParser(template=GRAPH_PROMPT_CN if lang == "cn" else GRAPH_PROMPT_EN),
#     searcher_cfg=dict(
#         llm=llm,
#         plugins=plugins,
#         template=date,
#         output_format=PluginParser(
#             template=searcher_system_prompt_cn if lang == "cn" else searcher_system_prompt_en,
#             tool_info=get_plugin_prompt(plugins),
#         ),
#         user_input_template=searcher_input_template_cn
#         if lang == "cn"
#         else searcher_input_template_en,
#         user_context_template=searcher_context_template_cn
#         if lang == "cn"
#         else searcher_context_template_en,
#     ),
#     summary_prompt=FINAL_RESPONSE_CN if lang == "cn" else FINAL_RESPONSE_EN,
#     max_turn=10,
# )

# for agent_return in agent("上海今天适合穿什么衣服"):
#     pass

# print(agent_return.sender)
# print(agent_return.content)
# print(agent_return.formatted["ref2url"])