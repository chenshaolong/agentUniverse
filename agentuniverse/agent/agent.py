# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2024/3/12 19:36
# @Author  : heji
# @Email   : lc299034@antgroup.com
# @FileName: agent.py
"""The definition of agent paradigm."""
import json
from abc import abstractmethod
from datetime import datetime
from typing import Optional

from langchain_core.utils.json import parse_json_markdown

from agentuniverse.agent.agent_model import AgentModel
from agentuniverse.agent.input_object import InputObject
from agentuniverse.agent.output_object import OutputObject
from agentuniverse.agent.plan.planner.planner import Planner
from agentuniverse.agent.plan.planner.planner_manager import PlannerManager
from agentuniverse.base.component.component_base import ComponentBase
from agentuniverse.base.component.component_enum import ComponentEnum
from agentuniverse.base.config.application_configer.application_config_manager \
    import ApplicationConfigManager
from agentuniverse.base.config.component_configer.configers.agent_configer \
    import AgentConfiger
from agentuniverse.base.util.logging.logging_util import LOGGER
from agentuniverse.llm.llm import LLM


class Agent(ComponentBase):
    """The parent class of all agent models, containing only attributes."""

    agent_model: Optional[AgentModel] = None

    def __init__(self):
        """Initialize the AgentModel with the given keyword arguments."""
        super().__init__(component_type=ComponentEnum.AGENT)

    @abstractmethod
    def input_keys(self) -> list[str]:
        """Return the input keys of the Agent."""
        pass

    @abstractmethod
    def output_keys(self) -> list[str]:
        """Return the output keys of the Agent."""
        pass

    @abstractmethod
    def parse_input(self, input_object: InputObject, agent_input: dict) -> dict:
        """Agent parameter parsing.

        Args:
            input_object (InputObject): input parameters passed by the user.
            agent_input (dict): agent input preparsed by the agent.
        Returns:
            dict: agent input parsed from `input_object` by the user.
        """
        pass

    @abstractmethod
    def parse_result(self, planner_result: dict) -> dict:
        """Planner result parser.

        Args:
            planner_result(dict): Planner result
        Returns:
            dict: Agent result object.
        """
        pass

    def run(self, **kwargs) -> OutputObject:
        """Agent instance running entry.

        Returns:
            OutputObject: Agent execution result
        """
        self.input_check(kwargs)
        input_object = InputObject(kwargs)

        agent_input = self.pre_parse_input(input_object)

        planner_result = self.execute(input_object, agent_input)

        agent_result = self.parse_result(planner_result)

        self.output_check(agent_result)
        output_object = OutputObject(agent_result)
        return output_object

    def execute(self, input_object: InputObject, agent_input: dict) -> dict:
        """Execute agent instance.

        Args:
            input_object (InputObject): input parameters passed by the user.
            agent_input (dict): agent input parsed from `input_object` by the user.

        Returns:
            dict: planner result generated by the planner execution.
        """

        planner_base: Planner = PlannerManager().get_instance_obj(self.agent_model.plan.get('planner').get('name'))
        planner_result = planner_base.invoke(self.agent_model, agent_input, input_object)
        return planner_result

    def pre_parse_input(self, input_object) -> dict:
        """Agent execution parameter pre-parsing.

        Args:
            input_object (InputObject): input parameters passed by the user.
        Returns:
            dict: agent input preparsed by the agent.
        """
        agent_input = dict()
        agent_input['chat_history'] = input_object.get_data('chat_history') or ''
        agent_input['background'] = input_object.get_data('background') or ''
        agent_input['image_urls'] = input_object.get_data('image_urls') or []
        agent_input['date'] = datetime.now().strftime('%Y-%m-%d')

        self.parse_input(input_object, agent_input)
        return agent_input

    def get_instance_code(self) -> str:
        """Return the full name of the agent."""
        appname = ApplicationConfigManager().app_configer.base_info_appname
        name = self.agent_model.info.get('name')
        return (f'{appname}.'
                f'{self.component_type.value.lower()}.{name}')

    def input_check(self, kwargs: dict):
        """Agent parameter check."""
        for key in self.input_keys():
            if key not in kwargs.keys():
                raise Exception(f'Input must have key: {key}.')

    def output_check(self, kwargs: dict):
        """Agent result check."""
        if not isinstance(kwargs, dict):
            raise Exception('Output type must be dict.')
        for key in self.output_keys():
            if key not in kwargs.keys():
                raise Exception(f'Output must have key: {key}.')

    def initialize_by_component_configer(self, component_configer: AgentConfiger) -> 'Agent':
        """Initialize the LLM by the ComponentConfiger object.

        Args:
            component_configer(LLMConfiger): the ComponentConfiger object
        Returns:
            LLM: the LLM object
        """
        agent_config: Optional[AgentConfiger] = component_configer.load()
        info: Optional[dict] = agent_config.info
        profile: Optional[dict] = agent_config.profile
        plan: Optional[dict] = agent_config.plan
        memory: Optional[dict] = agent_config.memory
        action: Optional[dict] = agent_config.action
        agent_model: Optional[AgentModel] = AgentModel(info=info, profile=profile,
                                                       plan=plan, memory=memory, action=action)
        self.agent_model = agent_model
        return self

    def langchain_run(self, input: str, callbacks=None, **kwargs):
        """Run the agent model using LangChain."""
        try:
            parse_result = parse_json_markdown(input)
        except Exception as e:
            LOGGER.error(f"langchain run parse_json_markdown error,input(parse_result) error({str(e)})")
            return "Error , Your Action Input is not a valid JSON string"
        output_object = self.run(**parse_result, callbacks=callbacks, **kwargs)
        result_dict = {}
        for key in self.output_keys():
            result_dict[key] = output_object.get_data(key)
        return result_dict

    def as_langchain_tool(self):
        """Convert to LangChain tool."""
        from langchain.agents.tools import Tool
        format_dict = {}
        for key in self.input_keys():
            format_dict.setdefault(key, "input val")
        format_str = json.dumps(format_dict)

        args_description = f"""
        to use this tool,your input must be a json string,must contain all keys of {self.input_keys()},
        and the value of the key must be a json string,the format of the json string is as follows:
        ```{format_str}```
        """
        return Tool(
            name=self.agent_model.info.get("name"),
            func=self.langchain_run,
            description=self.agent_model.info.get("description") + args_description
        )
