from typing import List, Tuple, Dict
from collections import Counter
import pretty_midi
import matplotlib.pyplot as plt
import librosa.display
import os
from os import listdir, walk
from os.path import isfile, isdir, join
from sys import argv
import traceback
import logging
import numpy as np


# Ideas behind the preprocessing class
#
# 1. only use those midi with one tempo and one key, since some midi music
# have key and tempo changes inside. Which might make some unpredictable result
#
# 2. list distribution for all keys contained in the corpus. Only select those
# most frequent appeared. (different keys may increase training difficulty)
#
# 3. only select similar tempo music, based on the mean and std of tempos,
# simple one will be left boundary = mean - std, right boundary = mean + std
#
# 4. find the mean of highest and lowest pitch in the corpus. filter out those not
# the range. We have pitch range from 0-128, no meaning cover two extreme sides.
class FileReport(object):
    """
    This class is mainly for generating meta information for our report
    """

    def __init__(self,
                 tempos: List[float],
                 freq_key: Dict[int, int],
                 min_pitch: List[int],
                 max_pitch: List[int]):
        self.tempos = tempos
        self.freq_key = freq_key
        self.min_pitch = min_pitch
        self.max_pitch = max_pitch

    def aggregation_report(self):
        """
        two important variable are min_pitch and max_pitch,
        since they will be used to decode from pitch to audio
        """
        temp_mean = np.array(self.tempos).mean()
        temp_std = np.array(self.tempos).std()
        most_freq_key = self.get_most_freq_value(self.freq_key)
        min_pitch = int(np.array(self.min_pitch).mean())
        max_pitch = int(np.array(self.max_pitch).mean())
        return temp_mean, temp_std, most_freq_key, min_pitch, max_pitch

    def plots(self):
        # implement later on
        pass

    def get_most_freq_value(self, keys: Dict[int, int], reversed=True) -> int:
        return sorted(keys.items(), key=lambda kv: kv[1], reverse=reversed)[0][0]


class Preprocess(object):
    def __init__(self, argv: List[str]):
        self.argv = argv
        self._cli_arg_parser()
        self._file_filter()

    def generate_midi_files_report(self) -> FileReport:
        """
        meta information like tempos, keys, pitches will be generated for
        filtering the midi files
        """
        tempos = []
        keys = []
        max_pitchs = []
        min_pitchs = []
        for pm in self.pms:
            tempos.append(pm.estimate_tempo())
            key = pm.key_signature_changes[0].key_number
            keys.append(key)
            min_pitch, max_pitch = self._get_min_max_pitch(pm)
            max_pitchs.append(max_pitch)
            min_pitchs.append(min_pitch)
        self.report = FileReport(tempos, dict(
            Counter(keys)), min_pitchs, max_pitchs)
        return self.report

    def _get_min_max_pitch(self, pm: pretty_midi.PrettyMIDI):
        """
        find the min and max pitch inside a midi file
        """
        notes = [
            note.pitch for instrument in pm.instruments for note in instrument.notes
        ]
        return min(notes), max(notes)

    def piano_roll_filter(self) -> np.array:
        """
        according generated meta data info to filter out those not in range
        """
        report = self.generate_midi_files_report()
        temp_mean, temp_std, key, left_pitch_bounary, right_pitch_boundary = report.aggregation_report()
        piano_rolls = []
        for pm in self.pms:
            tempo = pm.estimate_tempo()
            min_pitch, max_pitch = self._get_min_max_pitch(pm)
            if self._is_in_tempo_range(tempo,
                                       temp_mean,
                                       temp_std) and self._is_in_pitch_range(min_pitch,
                                                                             max_pitch,
                                                                             left_pitch_bounary,
                                                                             right_pitch_boundary):
                piano_roll = pm.get_piano_roll(
                )[left_pitch_bounary: right_pitch_boundary+1]
                piano_rolls.append(piano_roll)
        result = np.hstack(piano_rolls)
        return result.T

    def _is_in_tempo_range(self, tempo: float, mean: float, std: float) -> bool:
        """
        a helper function that can be used check if a midi file's tempo in range
        """
        if tempo > (mean - std) and tempo < (mean + std):
            return True
        return False

    def _is_in_pitch_range(self, low_pitch: int,
                           high_pitch: int,
                           left_boundary: int,
                           right_boundary: int) -> bool:
        if low_pitch >= left_boundary and high_pitch <= right_boundary:
            return True
        return False

    def _file_filter(self):
        """
        first filtering that only allow one tempo and one key inside a midi file
        """
        self.pms: List[pretty_midi.PrettyMIDI] = []
        for (dirPath, _, files) in walk(self.path):  # type: ignore
            for file in files:
                # get the absoluted path of file
                path = join(dirPath, file)
                try:
                    pm = pretty_midi.PrettyMIDI(path)
                    # only handle files contain one key and one tempo
                    if len(pm.key_signature_changes) == 1 and len(pm.time_signature_changes) == 1:
                        self.pms.append(pm)
                except:  # skip all parsing exceptions
                    pass

    def _cli_arg_parser(self):
        if len(self.argv) != 2:
            raise ValueError(f"path of folder must be provided")
        if isdir(self.argv[1]):
            path = os.path.abspath(argv[1])
            self.path = path
        else:
            raise ValueError(f"provided path is not a folder")


if __name__ == "__main__":
    try:
        p = Preprocess(argv)
        result = p.piano_roll_filter()
        print(result.shape)
    except Exception as err:
        logging.error(traceback.format_exc())
        exit(1)
