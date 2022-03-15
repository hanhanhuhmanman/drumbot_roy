import io
from typing import List, Optional, Generator

import miditoolkit.midi.parser as midi_parser
from miditoolkit.midi.parser import MidiFile
from miditoolkit.midi.containers import TimeSignature


class SampleExtractor:
    def __init__(self, bars_per_sample: int = 2) -> None:
        self.bars_per_sample = bars_per_sample

    def extract_samples(
        self,
        midi_obj: MidiFile,
    ) -> Generator[MidiFile, None, None]:
        if len(midi_obj.time_signature_changes) == 0:
            return None

        start = 0
        end = 0

        while start < midi_obj.max_tick:
            for _ in range(self.bars_per_sample):
                time_sig = self.get_time_signature_at_tick(
                    tick=end, time_signatures=midi_obj.time_signature_changes
                )
                fourths_per_bar = time_sig.numerator / (time_sig.denominator / 4)
                end += fourths_per_bar * midi_obj.ticks_per_beat

            stream = io.BytesIO()
            midi_obj.dump(file=stream, segment=(start, end))
            stream.seek(0)
            sample = midi_parser.MidiFile(file=stream)
            yield sample

            start = end

    def get_time_signature_at_tick(
        self, tick: int, time_signatures: List[TimeSignature]
    ) -> Optional[TimeSignature]:
        if len(time_signatures) == 0:
            return
        time_sig_at_tick = time_signatures[0]
        for time_sig in time_signatures[1:]:
            if tick >= time_sig.time:
                return time_sig_at_tick
