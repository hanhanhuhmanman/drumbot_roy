import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from miditok import Octuple
from torch.utils.data import Dataset
from miditoolkit.midi import parser as midi_parser
from tqdm.auto import tqdm

from src.drumbot_roy.training.sample_extractor import SampleExtractor

logger = logging.getLogger(__name__)


@dataclass
class RawSample:
    file_path: Path
    start: int
    end: int
    midi: midi_parser.MidiFile


@dataclass
class TokenizedSample:
    file_path: Path
    start: int
    end: int
    tokens: List[List[int]]


@dataclass
class TokenizedSamplePair:
    sample_a: TokenizedSample
    sample_b: TokenizedSample
    distance: float


class DrumSampleDataset(Dataset):
    def __init__(
        self,
        input_dir: Path,
        bars_per_sample: int,
        paired: bool = False,
        filter_out_empty_samples: bool = True,
        shuffle_files: bool = True,
        shuffle_seed: int = 42,
        only_drum: bool = True
    ) -> None:
        self.midi_file_paths = list(input_dir.rglob("*.mid")) + list(
            input_dir.rglob("*.midi")
        )

        random.seed(shuffle_seed)
        if shuffle_files:
            random.shuffle(self.midi_file_paths)

        self.paired = paired
        self.filter_out_empty_samples = filter_out_empty_samples
        self.only_drum = only_drum

        self.samples: Optional[List[RawSample]] = None
        self.sample_extractor = SampleExtractor(bars_per_sample=bars_per_sample)

        self.tokenizer = Octuple(nb_velocities=8)

    def prepare_samples(self):
        for midi_file_path in tqdm(self.midi_file_paths):
            for sample in self.sample_extractor.extract_samples(
                midi_file_path=midi_file_path,
                only_drum=self.only_drum
            ):
                number_of_notes = self.sample_extractor.get_number_of_notes(
                    midi_obj=sample.midi
                )
                if self.filter_out_empty_samples and number_of_notes == 0:
                    continue

                self.samples.append(sample)

    def __len__(self) -> Optional[int]:
        if self.samples is None:
            logger.warning(
                "Please run DrumSampleDataset.prepare_samples first "
                "to preprocess the samples."
            )
        elif not self.paired:
            return len(self.samples)
        else:
            # For each sample we generate one same-song pair
            # and one different-song pair
            return len(self.samples) * 2

    def __getitem__(
        self, item
    ) -> Optional[Union[TokenizedSample, TokenizedSamplePair]]:
        if self.samples is None:
            logger.warning(
                "Please run DrumSampleDataset.prepare_samples first "
                "to preprocess the samples."
            )
            return

        if not self.paired:
            sample = self.samples[item]
            return TokenizedSample(
                file_path=sample.file_path,
                start=sample.start,
                end=sample.end,
                tokens=self.tokenizer.midi_to_tokens(sample.midi),
            )
        else:
            sample_a = self.samples[item // 2]
            distance = 1
            if item % 2 == 0:
                sample_b_idx = (item // 2) + 1
                if (
                    sample_b_idx >= len(self)
                    or self.samples[sample_b_idx].file_path != sample_a.file_path
                ):
                    sample_b_idx = (item // 2) - 1

                sample_b = self.samples[sample_b_idx]
                if sample_a.file_path == sample_b.file_path:
                    distance = 0
            else:
                sample_b = self.samples[int((item + (len(self) / 2)) % len(self))]

            return TokenizedSamplePair(
                sample_a=TokenizedSample(
                    file_path=sample_a.file_path,
                    start=sample_a.start,
                    end=sample_a.end,
                    tokens=self.tokenizer.midi_to_tokens(sample_a.midi),
                ),
                sample_b=TokenizedSample(
                    file_path=sample_b.file_path,
                    start=sample_b.start,
                    end=sample_b.end,
                    tokens=self.tokenizer.midi_to_tokens(sample_b.midi),
                ),
                distance=distance,
            )
