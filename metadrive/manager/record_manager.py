import copy
import logging

from metadrive.constants import ObjectState
from metadrive.manager.base_manager import BaseManager
from metadrive.utils.map_utils import is_map_related_instance, is_map_related_class


class FrameInfo:
    def __init__(self, episode_step):
        self.episode_step = episode_step
        # used to track the objects spawn info
        self.spawn_info = {}
        # used to track update objects state in the scene
        self.step_info = {}
        # used to track the objects cleared
        self.clear_info = []
        self.agents = []
        self._object_to_agent = None
        self._agent_to_object = None

    def object_to_agent(self, object):
        return self._object_to_agent[object]

    def agent_to_object(self, agent):
        return self._agent_to_object[agent]


class RecordManager(BaseManager):
    """
    Record the episode information for replay
    """
    PRIORITY = 100  # lowest priority

    def __init__(self):
        super(RecordManager, self).__init__()
        self.episode_info = None
        self.current_frames = None
        self.current_step = 0
        self.reset_frame = None

    def before_reset(self):
        if self.engine.record_episode:
            self.episode_info = {}
            self.reset_frame = FrameInfo(self.engine.episode_step)

    def after_reset(self):
        """
        create a new log to record, note: after_step will be called after calling after_reset()
        """
        if self.engine.record_episode:
            self._update_objects_states()
            self.episode_info = dict(
                map_data=self.engine.current_map.save_map(),
                frame=[self.reset_frame],
            )
            self.current_frames = None
            self.reset_frame = None
            self.current_step = 0

    def before_step(self, *args, **kwargs) -> dict:
        if self.engine.record_episode:
            self.current_frames = [
                FrameInfo(self.engine.episode_step) for _ in range(self.engine.global_config["decision_repeat"])
            ]
            self.current_step = 0
        return {}

    def step(self, *args, **kwargs):
        if self.engine.record_episode:
            self._update_objects_states()
            self.current_step += 1 if self.current_step < len(self.current_frames) - 1 else 0
            # self.episode_info["frame"].append(self.current_frames.pop())

    def after_step(self, *args, **kwargs) -> dict:
        if self.engine.record_episode and self.current_step:
            self.episode_info["frame"] += self.current_frames
        return {}

    def _update_objects_states(self):
        for name, obj in self.engine.get_objects().items():
            if not is_map_related_instance(obj):
                self.current_frame.step_info[name] = obj.get_state()
        self.current_frame.agents = list(self.engine.agents.keys())
        self.current_frame._agent_to_object = self.engine.agent_manager._agent_to_object
        self.current_frame._object_to_agent = self.engine.agent_manager._object_to_agent

    def dump_episode(self):
        assert self.engine.record_episode, "Turn on recording episode and then dump it"
        return copy.deepcopy(self.episode_info)

    def destroy(self):
        self.episode_info = None

    def add_spawn_info(self, object_class, kwargs, name):
        """
        Call when spawn new objects, ignore map related things
        """
        if not is_map_related_class(object_class) and self.engine.record_episode:
            assert name not in self.current_frame.spawn_info, "Duplicated record!"
            self.current_frame.spawn_info[name] = {
                ObjectState.CLASS: object_class,
                ObjectState.INIT_KWARGS: kwargs,
                ObjectState.NAME: name
            }

    def add_clear_info(self, obj):
        """
        Call when clear objects, ignore map related things
        """
        if not is_map_related_instance(obj) and self.engine.record_episode:
            self.current_frame.clear_info.append(obj.name)

    def __del__(self):
        logging.debug("Record system is destroyed")

    @property
    def current_frame(self):
        return self.current_frames[self.current_step] if self.reset_frame is None else self.reset_frame
