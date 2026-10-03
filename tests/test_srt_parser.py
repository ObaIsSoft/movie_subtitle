import unittest

from srt_parser import parse_srt, decode_srt_bytes


def block(text, index=1, start='00:00:01,000', end='00:00:02,000'):
    return f"{index}\n{start} --> {end}\n{text}\n"


def texts(srt):
    return [sub['text'] for sub in parse_srt(srt)]


class ParseSrtTests(unittest.TestCase):
    def test_basic_block(self):
        self.assertEqual(parse_srt(block("You talking to me?")), [
            {'start': '00:00:01,000', 'end': '00:00:02,000', 'text': 'You talking to me?'}
        ])

    def test_block_without_index_line(self):
        self.assertEqual(texts("00:00:01,000 --> 00:00:02,000\nYou talking to me, pal?\n"),
                         ["You talking to me, pal?"])

    def test_whitespace_only_separator_line(self):
        srt = block("First line of dialogue") + " \n" + block("Second line of dialogue", index=2)
        self.assertEqual(texts(srt), ["First line of dialogue", "Second line of dialogue"])

    def test_keeps_two_word_quotes_and_drops_one_word_lines(self):
        srt = block("Here's Johnny!") + "\n" + block("Okay.", index=2)
        self.assertEqual(texts(srt), ["Here's Johnny!"])

    def test_multiline_text_is_joined(self):
        self.assertEqual(texts(block("I'll be\nback soon")), ["I'll be back soon"])

    def test_strips_tags_including_unclosed_ones(self):
        self.assertEqual(texts(block("<i>hello there</i> <img src=x onerror=alert`1`")), ["hello there"])

    def test_strips_styling_codes(self):
        self.assertEqual(texts(block("{\\an8}Look up here")), ["Look up here"])

    def test_removes_sound_effects(self):
        self.assertEqual(texts(block("[music playing] (sighs) We have to go")), ["We have to go"])

    def test_removes_speaker_labels(self):
        self.assertEqual(texts(block("MAN 1: Get down now")), ["Get down now"])
        self.assertEqual(texts(block("DR. JONES: Follow me")), ["Follow me"])

    def test_keeps_times_and_short_capitals(self):
        self.assertEqual(texts(block("10:30 is when we leave")), ["10:30 is when we leave"])
        self.assertEqual(texts(block("A 10:30 meeting again")), ["A 10:30 meeting again"])

    def test_dialogue_dashes_split_speakers(self):
        self.assertEqual(texts(block("- Are you coming with us?\n- No, I am staying.")),
                         ["Are you coming with us?", "No, I am staying."])

    def test_keeps_dashes_inside_a_line(self):
        self.assertEqual(texts(block("Well - I think so")), ["Well - I think so"])

    def test_long_lines_kept_whole(self):
        self.assertEqual(len(texts(block("word " * 120))[0].split()), 120)

    def test_dot_millisecond_separator_normalized(self):
        subs = parse_srt(block("Over here, quickly", start='0:00:01.500', end='0:00:02.000'))
        self.assertEqual((subs[0]['start'], subs[0]['end']), ('0:00:01,500', '0:00:02,000'))


class DecodeSrtBytesTests(unittest.TestCase):
    def test_utf8_with_bom(self):
        self.assertTrue(decode_srt_bytes("﻿1\nhi".encode('utf-8')).startswith("1"))

    def test_cp1252_smart_quotes(self):
        self.assertEqual(decode_srt_bytes("It’s here".encode('cp1252')), "It’s here")


if __name__ == '__main__':
    unittest.main()
