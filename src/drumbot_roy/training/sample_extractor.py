import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Generator

import miditoolkit.midi.parser as midi_parser
from miditoolkit.midi import parser as midi_parser
from miditoolkit.midi.parser import MidiFile
from miditoolkit.midi.containers import TimeSignature, Instrument

logger = logging.getLogger(__name__)


@dataclass
class RawSample:
    file_path: Path
    start: int
    end: int
    midi: midi_parser.MidiFile


class SampleExtractor:
    def __init__(self, bars_per_sample: int = 2) -> None:
        self.bars_per_sample = bars_per_sample

    def extract_samples(
        self,
        midi_file_path: Path,
        midi_obj: Optional[MidiFile] = None,
        only_drum: bool = False,
    ) -> Generator[RawSample, None, None]:
        if midi_obj is None:
            try:
                midi_obj = MidiFile(filename=midi_file_path)
            except Exception as exception:
                logger.warning(exception)
                return None

        if len(midi_obj.time_signature_changes) == 0:
            return None

        if only_drum:
            midi_obj.instruments = [
                instrument
                for instrument in midi_obj.instruments
                if instrument.is_drum
            ]

        if len(midi_obj.instruments) == 0:
            return None

        start = 0
        end = 0

        while start < midi_obj.max_tick:
            for _ in range(self.bars_per_sample):
                time_sig = self.get_time_signature_at_tick(
                    tick=end, time_signatures=midi_obj.time_signature_changes
                )
                if not time_sig:
                    return None
                fourths_per_bar = time_sig.numerator / (time_sig.denominator / 4)
                end += int(fourths_per_bar * midi_obj.ticks_per_beat)

            try:
                stream = io.BytesIO()
                midi_obj.dump(file=stream, segment=(start, end))
                stream.seek(0)
                sample = midi_parser.MidiFile(file=stream)
                yield RawSample(
                    file_path=midi_file_path, start=start, end=end, midi=sample
                )
            except Exception as exception:
                logger.warning(exception)

            start = end

    def get_time_signature_at_tick(
        self, tick: int, time_signatures: List[TimeSignature]
    ) -> Optional[TimeSignature]:
        if len(time_signatures) == 0:
            return
        time_sig_at_tick = time_signatures[0]
        for time_sig in time_signatures[1:]:
            if tick >= time_sig.time:
                time_sig_at_tick = time_sig
            else:
                break
        return time_sig_at_tick

    def get_number_of_notes(self, midi_obj: MidiFile) -> int:
        return len(
            [note for instrument in midi_obj.instruments for note in instrument.notes]
        )
