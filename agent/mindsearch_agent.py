from copy import deepcopy
from typing import Dict, List, Generator
import logging
import json
import re
from lagent.schema import AgentMessage, AgentStatusCode, ModelStatusCode, ActionStatusCode
import sys
sys.path.append('.')

from .graph import ExecutionAction, WebSearchGraph
from .streaming import StreamingAgentForInternLM,StreamingAgent


def _update_ref(ref: str, ref2url: Dict[str, str], ptr: int) -> str:
    numbers = list({int(n) for n in re.findall(r"\[\[(\d+)\]\]", ref)})
    numbers = {n: idx + 1 for idx, n in enumerate(numbers)}
    updated_ref = re.sub(
        r"\[\[(\d+)\]\]",
        lambda match: f"[[{numbers[int(match.group(1))] + ptr}]]",
        ref,
    )
    updated_ref2url = {}
    if numbers:
        try:
            assert all(elem in ref2url for elem in numbers)
        except Exception as exc:
            logging.info(f"Illegal reference id: {str(exc)}")
        if ref2url:
            updated_ref2url = {
                numbers[idx] + ptr: ref2url[idx] for idx in numbers if idx in ref2url
            }
    return updated_ref, updated_ref2url, len(numbers) + 1


# 生成参考信息
def _generate_references_from_graph(graph: Dict[str, dict]) -> tuple[str, Dict[int, dict]]:

    with open("record graph.json","w") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    ptr, references, references_url = 0, [], {}
    for name, data_item in graph.items():
        if name in ["root", "response"]:
            continue
        # only search once at each node, thus the result offset is 2
        print("\n")
        print("mindsearch_agent data_item:",data_item["memory"]["agent.memory"][-1])
        # assert data_item["memory"]["agent.memory"][2]["sender"].endswith("ActionExecutor")
        def parse(content):
            start = content.find("<|plugin|>") + len("<|plugin|>")
            end = content.find("<|action_end|>")
            return content[start:end] 
        reference = data_item["memory"]["agent.memory"][-1]["content"]
        # ref2url = {
        #     int(k): v
        #     for k, v in json.loads(parse(data_item["memory"]["agent.memory"][-1]["content"])).items()
        # }
        # updata_ref, ref2url, added_ptr = _update_ref(
        #     data_item["response"]["content"], ref2url, ptr
        # )
        # ptr += added_ptr
        # references.append(f'## {data_item["content"]}\n\n{updata_ref}')
        # references_url.update(ref2url)
    # return "\n\n".join(references), references_url
    return reference

class GeneratorWithReturn:
    """Generator wrapper to capture the return value."""

    def __init__(self, generator: Generator):
        self.generator = generator
        self.ret = None

    def __iter__(self):
        self.ret = yield from self.generator
        return self.ret



class MindSearchAgent(StreamingAgentForInternLM):
    def __init__(
        self,
        searcher_cfg: dict,
        summary_prompt: str,
        finish_condition=lambda m: "add_response_node" in m.content,
        max_turn: int = 10,
        **kwargs,
    ):
        WebSearchGraph.SEARCHER_CONFIG = searcher_cfg
        print("mindsearch kwargs:",kwargs)
        super().__init__(plugins=searcher_cfg['plugins'],finish_condition=finish_condition, max_turn=max_turn, **kwargs)
        self.summary_prompt = summary_prompt # 总结的prompt，用于生成最终总结内容
        self.action = ExecutionAction()

    def forward(self, message: AgentMessage, session_id=0, **kwargs):
        if isinstance(message, str):
            message = AgentMessage(sender="user", content=message)

        _graph_state = dict(node={}, adjacency_list={}, ref2url={})
        local_dict, global_dict = {}, globals()

        # 代理会执行最多 max_turn 回合的操作，每回合通过 self.agent() 生成新消息
        for _ in range(self.max_turn):
            # 查询和更新图状态

            print(f"第{_}次回合，message:{message}\n")

            last_agent_state = AgentStatusCode.SESSION_READY # 记录上一个代理的状态，用于更新当前消息的状态。
            # planner对整个查询进行plan
            for message in self.agent(message, session_id=session_id, **kwargs):   
                if isinstance(message.formatted,dict) and message.formatted.get("tool_type"):
                    if message.stream_state == ModelStatusCode.END:
                        message.stream_state = last_agent_state + int(
                            last_agent_state
                            in [
                                AgentStatusCode.CODING,
                                AgentStatusCode.PLUGIN_START,
                            ]
                        )
                    else:
                        message.stream_state = (
                            ActionStatusCode.PLUGIN_START
                            if message.formatted['tool_type'] == 'plugin'
                            else AgentStatusCode.CODING
                        )
                else:
                    message.stream_state = AgentStatusCode.STREAM_ING
                
                # 将图的状态（如节点和邻接列表）更新到当前消息的 formatted 字段
                message.formatted.update(deepcopy(_graph_state))
                # 返回消息给调用方（流式输出）
                yield message
                last_agent_state = message.stream_state


            # 如果消息的 tool_type 为空，表示没有更多的操作需要执行，设置消息的流状态为 END，然后返回
            print("planner message:",message)
            if not message.formatted['tool_type']:
                message.stream_state = AgentStatusCode.END
                yield message
                return
            
            # 否则，创建一个 GeneratorWithReturn 对象，调用 ExecutionAction.run() 来执行图节点查询操作，并获取结果。
            # searcher进行搜索
            gen = GeneratorWithReturn(
                self.action.run(message.content, local_dict, global_dict, False)
            )
    
            for graph_exec in gen:
                graph_exec.formatted["ref2url"] = deepcopy(_graph_state["ref2url"])
                yield graph_exec

            # 生成图的引用和 URL

            print("\n")
            print("nodes:",gen.ret[1])
            print("\n")
            print("adjacency_list:",gen.ret[2])
            print("\n")

            # reference, references_url = _generate_references_from_graph(gen.ret[1])
            
            reference = _generate_references_from_graph(gen.ret[1])

            _graph_state.update(node=gen.ret[1], adjacency_list=gen.ret[2], ref2url=None)
            
            # 如果满足结束条件，则创建一个新的总结消息
            if self.finish_condition(message):
                message = AgentMessage(
                    sender="ActionExecutor",
                    content=self.summary_prompt,
                    formatted=deepcopy(_graph_state),
                    stream_state=message.stream_state + 1, 
                )
                yield message
                for message in self.agent(message, session_id=session_id, **kwargs):
                    message.formatted.update(deepcopy(_graph_state))
                    yield message

                return
            
            # 如果没有满足结束条件，生成包含参考信息的消息，并返回
            message = AgentMessage(
                sender="ActionExecutor",
                content=reference,
                formatted=deepcopy(_graph_state),
                stream_state=message.stream_state + 1,  # plugin or code return
            )
            yield message




