#! /usr/bin/env python
#
# Tests for Audio.py
#
# NOTE: some tests will take a while.
#


"""Tests for Audio.py module"""


# Standard packages
import unittest


# Local packages
from mezcla.unittest_wrapper import TestWrapper
from mezcla import glue_helpers as gh
from mezcla import debug
from audio import Audio


# Test constants
AUDIOFILE = 'samples/test_audiofile.wav'


class TestIt(TestWrapper):
    """Class for testcase definition"""
    script_module     = TestWrapper.derive_tested_module_name(__file__)
    use_temp_base_dir = True
    maxDiff           = None


    # NOTE: this will take a while and this require a valid audio path in AUDIOFILE
    @unittest.skip("this will take a while and this require a valid audio path in AUDIOFILE")
    def test_sphinx_engine(self):
        """Test CMUSphinx speech recognition engine class"""
        debug.trace(debug.DETAILED, f"TestIt.test_sphinx_engine({self})")

        sample = Audio(AUDIOFILE)
        sample_speech = sample.get_speech(engine='sphinx')
        self.assertTrue(isinstance(sample_speech, str))
        self.assertTrue(sample_speech)


    def test_audio_path(self):
        """Test for audio.path"""
        debug.trace(debug.DETAILED, f"TestIt.test_audio_path({self})")

        path = 'some/path'

        sample = Audio(path)
        self.assertEqual(sample.get_path(), path)

        sample = Audio()
        self.assertTrue(not sample.get_path())
        sample.set_path(path)
        self.assertEqual(sample.get_path(), path)


    def test_source_single_audio(self):
        """End to end test sourcing a single audio file"""
        debug.trace(debug.DETAILED, f"TestIt.test_source_single_audio({self})")

        audio = self.temp_file + '.wav'
        gh.write_file(audio, 'some content')

        command  = f'python audio.py --verbose {audio}'
        expected = f'Audio founded: {audio}'
        self.assertEqual(gh.run(command), expected)


    def test_source_list(self):
        """End to end test sourcing a list of audio files"""
        debug.trace(debug.DETAILED, f"TestIt.test_source_list({self})")

        list_file = self.temp_file + '.list'

        audio_list = ('audio1.wav\n'
                      'audio2.wav\n'
                      'audio23.wav\n'
                      'audioN.wav')

        gh.write_file(list_file, audio_list)

        command  = f'python audio.py --verbose {list_file}'
        expected = ('Audio founded: audio1.wav\n'
                    'Audio founded: audio2.wav\n'
                    'Audio founded: audio23.wav\n'
                    'Audio founded: audioN.wav')
        self.assertEqual(gh.run(command), expected)


    def test_source_folder(self):
        """End to end test sourcing a folder and discover audiofiles"""
        debug.trace(debug.DETAILED, f"TestIt.test_source_folder({self})")

        ## TODO: resolve librosa find files recursively not woking.
        ## filenames = ['/audio1.wav', '/somedir/audio2.wav', '/audio23.wav']

        filenames = ['/audio1.wav', '/audio23.wav']
        for filename in filenames:
            gh.write_file(self.temp_base + filename, 'content')

        actual = gh.run(f'python audio.py --verbose {self.temp_base}')

        for filename in filenames:
            self.assertTrue(filename in actual)


    # NOTE: this will take a while and this require a valid audio path in AUDIOFILE
    @unittest.skip("this will take a while and this require a valid audio path in AUDIOFILE")
    def test_extract_speech(self):
        """End to end test extracting speech using CMUSphinx engine"""
        debug.trace(debug.DETAILED, f"TestIt.test_extract_speech({self})")

        actual = gh.run(f'python audio.py --verbose --speech sphinx {AUDIOFILE}')
        self.assertTrue('- speech recognized' in actual)
        self.assertTrue(isinstance(actual, str))
        self.assertTrue(actual)


if __name__ == '__main__':
    unittest.main()
