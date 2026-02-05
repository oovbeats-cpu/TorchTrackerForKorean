"""Time tracking service for play time measurement."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class PlayState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class PauseSettings:
    bag: bool = True
    pet: bool = True
    talent: bool = True
    settings: bool = True
    skill: bool = True
    auction: bool = True


@dataclass
class TimeTrackerState:
    total_play_state: PlayState
    total_play_seconds: float
    mapping_play_state: PlayState
    mapping_play_seconds: float
    auto_pause_on_inventory: bool
    current_map_start_time: Optional[datetime]
    surgery_count: int = 0
    avg_surgery_time_seconds: float = 0.0
    pause_settings: Optional[PauseSettings] = None
    surgery_prep_start_time: Optional[datetime] = None
    surgery_total_seconds: float = 0.0


class TimeTracker:
    """
    Tracks total play time and mapping time.
    
    Total play time:
    - User manually starts/stops via UI
    - Can auto-pause when inventory is opened (if enabled)
    - Resumes when inventory is closed
    
    Mapping play time:
    - Automatically tracks time spent in maps
    - Starts when entering a map, stops when leaving
    """
    
    def __init__(self) -> None:
        self._total_play_state = PlayState.STOPPED
        self._total_play_accumulated: timedelta = timedelta()
        self._total_play_start_time: Optional[datetime] = None
        
        self._mapping_state = PlayState.STOPPED
        self._mapping_accumulated: timedelta = timedelta()
        self._mapping_start_time: Optional[datetime] = None
        
        self._auto_pause_on_inventory = False
        self._was_playing_before_auto_pause = False
        self._was_mapping_before_pause = False
        
        self._surgery_prep_start_time: Optional[datetime] = None
        self._surgery_count = 0
        self._surgery_total_seconds: float = 0.0
        
        self._pause_settings = PauseSettings()
    
    @property
    def total_play_seconds(self) -> float:
        """Get total play time in seconds."""
        accumulated = self._total_play_accumulated.total_seconds()
        if self._total_play_state == PlayState.PLAYING and self._total_play_start_time:
            current_session = (datetime.now() - self._total_play_start_time).total_seconds()
            return accumulated + current_session
        return accumulated
    
    @property
    def mapping_play_seconds(self) -> float:
        """Get mapping play time in seconds."""
        accumulated = self._mapping_accumulated.total_seconds()
        if self._mapping_state == PlayState.PLAYING and self._mapping_start_time:
            current_session = (datetime.now() - self._mapping_start_time).total_seconds()
            return accumulated + current_session
        return accumulated
    
    @property
    def total_play_state(self) -> PlayState:
        return self._total_play_state
    
    @property
    def mapping_state(self) -> PlayState:
        return self._mapping_state
    
    @property
    def auto_pause_on_inventory(self) -> bool:
        return self._auto_pause_on_inventory
    
    @property
    def surgery_count(self) -> int:
        return self._surgery_count
    
    @property
    def avg_surgery_time_seconds(self) -> float:
        if self._surgery_count == 0:
            return 0.0
        return self._surgery_total_seconds / self._surgery_count
    
    def get_state(self) -> TimeTrackerState:
        """Get current state snapshot."""
        return TimeTrackerState(
            total_play_state=self._total_play_state,
            total_play_seconds=self.total_play_seconds,
            mapping_play_state=self._mapping_state,
            mapping_play_seconds=self.mapping_play_seconds,
            auto_pause_on_inventory=self._auto_pause_on_inventory,
            current_map_start_time=self._mapping_start_time,
            surgery_count=self._surgery_count,
            avg_surgery_time_seconds=self.avg_surgery_time_seconds,
            pause_settings=self._pause_settings,
            surgery_prep_start_time=self._surgery_prep_start_time,
            surgery_total_seconds=self._surgery_total_seconds,
        )
    
    @property
    def pause_settings(self) -> PauseSettings:
        """Get current pause settings."""
        return self._pause_settings
    
    def set_pause_settings(self, bag: Optional[bool] = None, pet: Optional[bool] = None, 
                           talent: Optional[bool] = None, settings: Optional[bool] = None, 
                           skill: Optional[bool] = None, auction: Optional[bool] = None) -> None:
        """Update pause settings for specific views."""
        if bag is not None:
            self._pause_settings.bag = bag
        if pet is not None:
            self._pause_settings.pet = pet
        if talent is not None:
            self._pause_settings.talent = talent
        if settings is not None:
            self._pause_settings.settings = settings
        if skill is not None:
            self._pause_settings.skill = skill
        if auction is not None:
            self._pause_settings.auction = auction
    
    def should_pause_for_view(self, view_name: str) -> bool:
        """Check if the given view should trigger auto-pause."""
        view_map = {
            "PCBagCtrl": self._pause_settings.bag,
            "PetCtrl": self._pause_settings.pet,
            "TalentCtrl": self._pause_settings.talent,
            "SettingCtrl": self._pause_settings.settings,
            "SkillCtrl": self._pause_settings.skill,
            "AuctionHouseV2Ctrl": self._pause_settings.auction,
        }
        return view_map.get(view_name, False)
    
    def start_total_play(self) -> None:
        """Start or resume total play time tracking."""
        if self._total_play_state != PlayState.PLAYING:
            self._total_play_state = PlayState.PLAYING
            self._total_play_start_time = datetime.now()
    
    def stop_total_play(self) -> None:
        """Stop total play time tracking."""
        if self._total_play_state == PlayState.PLAYING and self._total_play_start_time:
            elapsed = datetime.now() - self._total_play_start_time
            self._total_play_accumulated += elapsed
        self._total_play_state = PlayState.STOPPED
        self._total_play_start_time = None
    
    def pause_total_play(self) -> None:
        """Pause total play time (can be resumed)."""
        if self._total_play_state == PlayState.PLAYING and self._total_play_start_time:
            elapsed = datetime.now() - self._total_play_start_time
            self._total_play_accumulated += elapsed
        self._total_play_state = PlayState.PAUSED
        self._total_play_start_time = None
    
    def resume_total_play(self) -> None:
        """Resume paused total play time."""
        if self._total_play_state == PlayState.PAUSED:
            self._total_play_state = PlayState.PLAYING
            self._total_play_start_time = datetime.now()
    
    def toggle_total_play(self) -> PlayState:
        """Toggle between playing and stopped states."""
        if self._total_play_state == PlayState.PLAYING:
            self.stop_total_play()
        else:
            self.start_total_play()
        return self._total_play_state
    
    def set_auto_pause_on_inventory(self, enabled: bool) -> None:
        """Enable or disable auto-pause when inventory is opened."""
        self._auto_pause_on_inventory = enabled
    
    def on_inventory_opened(self) -> None:
        """Called when inventory is opened (detected from logs)."""
        if self._auto_pause_on_inventory and self._total_play_state == PlayState.PLAYING:
            self._was_playing_before_auto_pause = True
            self.pause_total_play()
    
    def on_inventory_closed(self) -> None:
        """Called when inventory is closed (detected from logs)."""
        if self._auto_pause_on_inventory and self._was_playing_before_auto_pause:
            self._was_playing_before_auto_pause = False
            self.resume_total_play()
    
    def on_ui_view_pause(self) -> None:
        """Called when a menu/UI view is opened (should pause time tracking)."""
        if self._total_play_state == PlayState.PLAYING:
            self._was_playing_before_auto_pause = True
            self.pause_total_play()
        if self._mapping_state == PlayState.PLAYING:
            self._was_mapping_before_pause = True
            self.pause_mapping()
    
    def on_ui_view_resume(self) -> None:
        """Called when returning to combat/gameplay view (FightCtrl)."""
        if self._was_playing_before_auto_pause:
            self._was_playing_before_auto_pause = False
            self.resume_total_play()
        if getattr(self, '_was_mapping_before_pause', False):
            self._was_mapping_before_pause = False
            self.resume_mapping()
    
    def pause_mapping(self) -> None:
        """Pause mapping time (can be resumed)."""
        if self._mapping_state == PlayState.PLAYING and self._mapping_start_time:
            elapsed = datetime.now() - self._mapping_start_time
            self._mapping_accumulated += elapsed
        self._mapping_state = PlayState.PAUSED
        self._mapping_start_time = None
    
    def resume_mapping(self) -> None:
        """Resume paused mapping time."""
        if self._mapping_state == PlayState.PAUSED:
            self._mapping_state = PlayState.PLAYING
            self._mapping_start_time = datetime.now()
    
    def on_map_start(self, timestamp: Optional[datetime] = None) -> None:
        """Called when entering a map."""
        if self._mapping_state != PlayState.PLAYING:
            self._mapping_state = PlayState.PLAYING
            self._mapping_start_time = timestamp or datetime.now()
    
    def on_map_end(self, timestamp: Optional[datetime] = None) -> None:
        """Called when leaving a map (entering hub/town)."""
        if self._mapping_state == PlayState.PLAYING and self._mapping_start_time:
            end_time = timestamp or datetime.now()
            elapsed = end_time - self._mapping_start_time
            self._mapping_accumulated += elapsed
        self._mapping_state = PlayState.STOPPED
        self._mapping_start_time = None
    
    def reset_mapping_time(self) -> None:
        """Reset mapping time counter."""
        self._mapping_accumulated = timedelta()
        if self._mapping_state == PlayState.PLAYING:
            self._mapping_start_time = datetime.now()
    
    def reset_total_time(self) -> None:
        """Reset total play time counter."""
        self._total_play_accumulated = timedelta()
        if self._total_play_state == PlayState.PLAYING:
            self._total_play_start_time = datetime.now()
    
    def reset_all(self) -> None:
        """Reset all time counters and stop all timers."""
        self.stop_total_play()
        self._total_play_accumulated = timedelta()
        self._mapping_state = PlayState.STOPPED
        self._mapping_start_time = None
        self._mapping_accumulated = timedelta()
        self._was_playing_before_auto_pause = False
        self._surgery_prep_start_time = None
        self._surgery_count = 0
        self._surgery_total_seconds = 0.0
    
    def on_surgery_prep_start(self, timestamp: Optional[datetime] = None) -> None:
        """Called when S13GamePlayMainCtrl view is detected (surgery prep starts).
        
        Only sets start time if not already in a surgery prep phase to avoid
        resetting the timer when the view event fires multiple times.
        """
        import logging
        logger = logging.getLogger(__name__)
        if self._surgery_prep_start_time is None:
            self._surgery_prep_start_time = timestamp or datetime.now()
            logger.info(f"Surgery prep started at {self._surgery_prep_start_time}, current count: {self._surgery_count}")
        else:
            logger.debug(f"Surgery prep already in progress since {self._surgery_prep_start_time}, ignoring duplicate event")
    
    def on_surgery_complete(self, timestamp: Optional[datetime] = None) -> None:
        """Called when S13GamePlayRewardCtrl view is detected after prep start."""
        import logging
        logger = logging.getLogger(__name__)
        if self._surgery_prep_start_time is not None:
            end_time = timestamp or datetime.now()
            prep_duration = (end_time - self._surgery_prep_start_time).total_seconds()
            self._surgery_total_seconds += prep_duration
            self._surgery_count += 1
            logger.info(f"Surgery complete: duration={prep_duration:.2f}s, count={self._surgery_count}, total={self._surgery_total_seconds:.2f}s")
            self._surgery_prep_start_time = None
        else:
            logger.debug(f"Surgery complete called but no prep start time recorded (count: {self._surgery_count})")
    
    def on_surgery_interrupted(self, timestamp: Optional[datetime] = None) -> None:
        """Called when FightCtrl is detected during surgery prep (user left surgery screen).
        
        Records the elapsed time as completed surgery since the time was still spent on surgery.
        """
        import logging
        logger = logging.getLogger(__name__)
        if self._surgery_prep_start_time is not None:
            end_time = timestamp or datetime.now()
            prep_duration = (end_time - self._surgery_prep_start_time).total_seconds()
            self._surgery_total_seconds += prep_duration
            self._surgery_count += 1
            logger.info(f"Surgery interrupted (FightCtrl): duration={prep_duration:.2f}s, count={self._surgery_count}, total={self._surgery_total_seconds:.2f}s")
            self._surgery_prep_start_time = None
    
    @property
    def is_in_surgery_prep(self) -> bool:
        """Check if currently in surgery prep phase."""
        return self._surgery_prep_start_time is not None
    
    def reset_surgery_stats(self) -> None:
        """Reset surgery statistics."""
        self._surgery_prep_start_time = None
        self._surgery_count = 0
        self._surgery_total_seconds = 0.0
