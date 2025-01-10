import os
from copy import deepcopy
from datetime import datetime
import sys

from lagent.actions import WebBrowser
from lagent.agents.stream import get_plugin_prompt
from lagent.prompts import InterpreterParser,PluginParser
from lagent.utils import create_object

sys.path.append('.')

from .models import gpt4
from .mindsearch_agent import MindSearchAgent
from .mindsearch_prompt import (
    FINAL_RESPONSE_CN,
    GRAPH_PROMPT_CN,
    searcher_context_template_cn,
    searcher_input_template_cn,
    searcher_system_prompt_cn,
)


def init_agent(lang="cn",model_format=gpt4, search_engine="BingSearch"):

    llm = create_object(gpt4)
    date = datetime.now().strftime("The current date is %Y-%m-%d.")
    
    # 搜索引擎
    plugins = [
        dict(
        type=WebBrowser,
        searcher_type=search_engine,
        topk=6,
        api_key=os.getenv("WEB_SEARCH_API_KEY"),
    )]

    # 智能体
    agent = MindSearchAgent(
        llm=llm,
        template=date,
        output_format=InterpreterParser(template=GRAPH_PROMPT_CN),
        searcher_cfg=dict(
            llm=llm,
            plugins=plugins,
            template=date,
            output_format=PluginParser(
                template=searcher_system_prompt_cn,
                tool_info=get_plugin_prompt(plugins),
            ),
            user_input_template=searcher_input_template_cn,
            user_context_template=searcher_context_template_cn,
        ),
        summary_prompt=FINAL_RESPONSE_CN,
        max_turn=10,
    )

    print("llm:",llm)
    print("plugins:",plugins)
    print("agent:",agent)
    return agent



if __name__ == "__main__":
    agent=init_agent()
    for agent_return in agent("上海今天适合穿什么衣服"):
        pass
    print(agent_return.sender)
    print(agent_return.content)
    print(agent_return.formatted["ref2url"])