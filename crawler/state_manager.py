import json
import time
from pathlib import Path
from typing import Optional
from loguru import logger

from crawler.models import CrawlState


class StateManager:
    
    def __init__(self, checkpoint_file: Path, auto_resume: bool = True):
        self.checkpoint_file = checkpoint_file
        self.auto_resume = auto_resume
        
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    
    def checkpoint_exists(self) -> bool:
        return self.checkpoint_file.exists() and self.auto_resume
    
    def load_checkpoint(self) -> Optional[CrawlState]:
        if not self.checkpoint_exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = CrawlState.from_dict(data)
            
            visited_count = len(state.visited)
            logger.info(f"Resuming from checkpoint: {visited_count:,} URLs visited")
            
            return state
            
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def save_checkpoint(self, state: CrawlState):
        tmp_file = self.checkpoint_file.with_suffix('.tmp')
        
        try:
            data = state.to_dict()
            data['timestamp'] = time.time()
            
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            tmp_file.replace(self.checkpoint_file)
            
            stats = state.get_statistics()
            logger.info(f"Checkpoint saved ({stats['pages_accepted']:,} pages)")
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            if tmp_file.exists():
                tmp_file.unlink()