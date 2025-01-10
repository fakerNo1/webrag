import queue
import random
import uuid
import re
from typing import Dict, List
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from lagent.actions import BaseAction
from lagent.schema import AgentMessage, AgentStatusCode, ModelStatusCode

from .streaming import StreamingAgentForInternLM


class SearcherAgent(StreamingAgentForInternLM):
    def __init__(
        self,
        user_input_template: str = "{question}",
        user_context_template: str = None,
        **kwargs,
    ):
        self.user_input_template = user_input_template
        self.user_context_template = user_context_template
        super().__init__(**kwargs)

    def forward(
        self,
        question: str, # 当前问题
        topic: str, # 主问题
        history: List[dict] = None, # 父问题的答案
        session_id=0,
        **kwargs,
    ):
        message = [self.user_input_template.format(question=question, topic=topic)]
        if history and self.user_context_template:
            message = [self.user_context_template.format_map(item) for item in history] + message
        message = "\n".join(message)
        return super().forward(message, session_id=session_id, **kwargs)


class WebSearchGraph:

    is_async = False
    SEARCHER_CONFIG = {}
    _SEARCHER_LOOP = []
    _SEARCHER_THREAD = []

    def __init__(self):
        self.nodes: Dict[str, Dict[str,str]] = {} # 存储图中所有节点的字典。每个节点由其名称索引，并包含内容、类型以及其他相关信息。
        self.adjacency_list: Dict[str, List[dict]] = defaultdict(list) # 存储图中所有节点之间连接关系的邻接表。每个节点由其名称索引，并包含一个相邻节点名称的列表。
        self.future_to_query = dict()
        self.searcher_resp_queue = queue.Queue() # 记录搜索队列
        self.executor = ThreadPoolExecutor(max_workers=10) # 这是一个字典，用于将提交的异步任务与相应的查询内容关联起来。它的键是 future 对象，值是查询的描述信息。
        self.n_active_tasks = 0

    def add_root_node(
        self,
        node_content : str,
        node_name: str = "root",
    ):
        """添加起始节点

        Args:
            node_content (str): 节点内容
            node_name (str, optional): 节点名称. Defaults to 'root'.

        """
        self.nodes[node_name] = dict(content=node_content, type="root")
        self.adjacency_list[node_name] = []
    
    def add_node(
        self,
        node_name: str,
        node_content: str,
    ):
        """添加搜索子问题节点

        Args:
            node_name (str): 节点名称
            node_content (str): 子问题内容

        Returns:
            str: 返回搜索结果
        """

        self.nodes[node_name] = dict(content=node_content, type="searcher")
        self.adjacency_list[node_name] = []

        # 获取父节点，以获得历史对话信息
        parent_nodes = []
        for start_node, adj in self.adjacency_list.items():
            for neighbor in adj:
                if(
                    node_name == neighbor
                    and start_node in self.nodes
                    and "response" in self.nodes[start_node]
                ):
                    parent_nodes.append(self.nodes[start_node])

        parent_response = [
            dict(question=node['content'], answer=node['response']) for node in parent_nodes
        ]

        # 进行搜索,获取节点的content内容
        def _search_node_stream():
            cfg = {
                **self.SEARCHER_CONFIG,
                "plugins": deepcopy(self.SEARCHER_CONFIG.get("plugins")),
            }
            agent, session_id = SearcherAgent(**cfg), random.randint(0,999999)
            searcher_message = AgentMessage(sender="SearcherAgent",content="")
            
            try:
                for searcher_message in agent(
                    question=node_content,
                    topic=self.nodes["root"]["content"],
                    history=parent_response,
                    session_id=session_id,
                ):
                    self.nodes[node_name]["response"] = searcher_message.model_dump()
                    self.nodes[node_name]["memory"] = agent.state_dict(session_id=session_id)
                    self.nodes[node_name]["session_id"] = session_id
                    self.searcher_resp_queue.put((node_name, self.nodes[node_name],[]))
                
                self.searcher_resp_queue.put((None,None,None))
            
            except Exception as exc:
                self.searcher_resp_queue.put((exc,None,None))
            
        self.future_to_query[
            self.executor.submit(_search_node_stream)
        ] = f"{node_name}-{node_content}"
            
        self.n_active_tasks += 1

    def add_response_node(self, node_name="response"):
        """添加回复节点
        如果当前获取的信息已经满足问题需求，添加回复节点。

        Args:
            thought (str): 思考过程
            node_name (str, optional): 节点名称. Defaults to 'response'.

        """
        self.nodes[node_name] = dict(type="end")
        self.searcher_resp_queue.put((node_name,self.nodes[node_name],[]))
    
    def add_edge(self, start_node:str, end_node:str):
        """添加边
        Args:
            start_node(str) : 起始节点名称
            end_node(str): 结束节点名称
        """
        self.adjacency_list[start_node].append(dict(id=str(uuid.uuid4()), name=end_node, state=2))
        self.searcher_resp_queue.put(
            (start_node, self.nodes[start_node],self.adjacency_list[start_node])
        )

    def reset(self):
        self.nodes = {}
        self.adjacency_list = defaultdict(list)
    
    def node(self, node_name:str) -> str:
        return self.nodes[node_name].copy()



class ExecutionAction(BaseAction):
    """Tool used by MindSearch planner to execute graph node query."""
    def run(self, command, local_dict, global_dict, stream_graph=False):
        # 抽取信息中的代码行
        def extract_code(text: str) -> str:
            text = re.sub(r"from ([\w.]+) import WebSearchGraph", "", text)
            triple_match = re.search(r"```[^\n]*\n(.+?)```", text, re.DOTALL)
            single_match = re.search(r"`([^`]*)`", text, re.DOTALL)
            if triple_match:
                return triple_match.group(1)
            elif single_match:
                return single_match.group(1)
            return text
        

        command = extract_code(command)
        # 执行图添加代码
        exec(command, global_dict, local_dict)
        
        # 匹配所有graph.node 中的内容
        node_list = re.findall(r"graph.node\((.*?)\)",command)

        graph:WebSearchGraph = local_dict["graph"] # graph类型为WebSearchGraph
        while graph.n_active_tasks:
            while not graph.searcher_resp_queue.empty():
                node_name, _, _ = graph.searcher_resp_queue.get(timeout=60)
                if isinstance(node_name, Exception):
                    raise node_name
                if node_name is None:
                    graph.n_active_tasks -= 1
                    continue
                # 流式图更新
                if stream_graph:
                    for neighbors in graph.adjacency_list.values():
                        for neighbor in neighbors:
                            # state 1进行中，2未开始，3已结束
                            if not(
                                neighbor["name"] in graph.nodes
                                and "response" in graph.nodes[neighbor["name"]]
                            ):
                                neighbor["state"] = 2
                            elif(
                                graph.nodes[neighbor["name"]["response"]["stream_state"]] == AgentStatusCode.END
                            ):
                                neighbor["state"] = 3
                            else:
                                neighbor["state"] = 1
                    if all(
                        "response" in node
                        for name, node in graph.nodes.items()
                        if name not in ["root", "response"]
                    ):
                        yield AgentMessage(
                            sender=self.name,
                            content=dict(current_node=node_name),
                            formatted=dict(
                                node=deepcopy(graph.nodes),
                                adjacency_list=deepcopy(graph.adjacency_list),
                            ),
                            stream_state=AgentStatusCode.STREAM_ING,
                        )


        res = [graph.nodes[node.strip().strip('"').strip(".")] for node in node_list]
        return res, graph.nodes, graph.adjacency_list
