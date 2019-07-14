#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# dog_whisperer is a small python script that uses gnuradio to hide encrypted data inside video files, using high frequency audio
# author - mamatb
# location - https://gitlab.com/mamatb/dog_whisperer.git

# TODO
#
# readme.md with screenshots and license
# show progress while encoding/decoding
# use colored output
# acknowledgements
# stop using global variables
# use more specific file names

# FUTURE WORK
#
# deal with videos having more than one audio stream or none at all
# offer different video formats to encode the data in
# use buffered readers and writers to reduce the number of disk accesses
# compress data before encoding into the audio
# allow more bits per sample, error rates are so low
# avoid using simple_aes_cipher as it wastes space by base64-encoding after encrypting
# use frequency hiding techniques such as FHSS or DSSS

# gnuradio imports
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio import filter as gnufilter
from gnuradio.filter import firdes

# other imports
import sys
import os
import time
import wave
import md5
from simple_aes_cipher import AESCipher, generate_secret_key

# some variables
program_name = 'dog_whisperer.py'
video_container = ''
input_file = ''
password = ''
tmp_audio_extracted = '/tmp/' + str(int(time.time())) + '_dog_whisperer_1.wav'
tmp_audio_modified = '/tmp/' + str(int(time.time())) + '_dog_whisperer_2.wav'
tmp_audio_converted = '/tmp/' + str(int(time.time())) + '_dog_whisperer.mp3'
tmp_data_encrypted = '/tmp/' + str(int(time.time())) + '_dog_whisperer_1.data'
tmp_data_formatted = '/tmp/' + str(int(time.time())) + '_dog_whisperer_2.data'
tmp_data_plain = '/tmp/' + str(int(time.time())) + '_dog_whisperer_3.data'
tmp_video_result = '/tmp/' + str(int(time.time())) + '_dog_whisperer.mp4'

# usage printing function
def print_usage():
    print 'USAGE:'
    print '\tpython ' + program_name + ' encode <input_file> <video_container> <password>'
    print '\tpython ' + program_name + ' decode <video_container> <password>'
    print '\n-- ' + program_name + ' is a small python script that uses gnuradio to hide encrypted data inside video files, using high frequency audio --'

# error printing function
def print_error(error_message):
    print 'ERROR:'
    print '\t' + error_message

# info printing function
def print_info(information):
    print 'INFO:'
    print '\t' + information

# success printing function
def print_success(message):
    print 'SUCCESS:'
    print '\t' + message

# dependencies checking function
def dependencies_check():
    dependencies = ['ffmpeg', 'lame']
    for binary in dependencies:
        ret = os.system(binary + ' --help > /dev/null 2>&1')
        if ret != 0:
            print_error('you need to have ' + binary + ' installed in order to run ' + program_name)
            print_info('installation in Debian-like distros: sudo apt install ' + binary)
            exit(1)

# arguments checking function
def arguments_check():

    global input_file
    global video_container
    global password

    # encoding
    if len(sys.argv) == 5:
        if sys.argv[1] == 'encode':
            if not os.access(sys.argv[2], os.R_OK) or not os.access(sys.argv[3], os.R_OK) or not os.access(sys.argv[3], os.W_OK):
                print_error('you need to have read permissions over the <input_file> as well as read and write permissions over the <video_container> when encoding with ' + program_name)
                print_usage()
                exit(1)
            else:
                input_file = sys.argv[2]
                video_container = sys.argv[3]
                password = sys.argv[4]
        else:
            print_error('wrong syntax for the encode option of ' + program_name)
            print_usage()
            exit(1)

    # decoding
    elif len(sys.argv) == 4:
        if sys.argv[1] == 'decode':
            if not os.access(sys.argv[2], os.R_OK):
                print_error('you need to have read permissions over the <video_container> when decoding with ' + program_name)
                print_usage()
                exit(1)
            else:
                video_container = sys.argv[2]
                password = sys.argv[3]
        else:
            print_error('wrong syntax for the decode option of ' + program_name)
            print_usage()
            exit(1)

    # error
    else:
        print_error('wrong number of arguments for ' + program_name)
        print_usage()
        exit(1)

# audio extraction function
def extract_video_audio():

    # audio extraction using the codec pcm_s16le (usual for .wav files), a sample frequency of 44100 Hz (better explained later) and one channel (mono audio)
    ret = os.system('ffmpeg -i ' + video_container + ' -vn -acodec pcm_s16le -ar 44100 -ac 1 ' + tmp_audio_extracted + ' > /dev/null 2>&1')
    if ret != 0:
        print_error('could not extract the audio from "' + video_container + '", please make sure it is a valid video file with audio or consider using a different one (rare video formats can pose problems)')
        print_usage()
        exit(1)

# aes encryption function
def aes_encryption():

    # padding, initialization vectors and password derivation is handled by the library
    key = generate_secret_key(password)
    cipher = AESCipher(key)
    local_file_reader = open(input_file, 'r')
    local_file_data = local_file_reader.read()
    local_file_reader.close()
    local_file_writer = open(tmp_data_encrypted, 'w')
    local_file_writer.write(cipher.encrypt(local_file_data))
    local_file_writer.close()

# aes decryption function
def aes_decryption():
    key = generate_secret_key(password)
    cipher = AESCipher(key)
    local_file_reader = open(tmp_data_encrypted, 'r')
    local_file_data = local_file_reader.read()
    local_file_reader.close()
    local_file_writer = open(tmp_data_plain, 'w')
    local_file_writer.write(cipher.decrypt(local_file_data))
    local_file_writer.close()
    print_success('the retrieved hidden data from "' + video_container + '" is located at "' + tmp_data_plain + '", this data will make sense as long as the password was correct')
    exit(0)

# data formatting function
def data_format():

    # the formatted data consists in a loop of (specific pattern + encrypted data + md5 hash)
    pattern = '\xde\xad\xbe\xef'
    encrypted_data_reader = open(tmp_data_encrypted, 'r')
    encrypted_data = encrypted_data_reader.read()
    encrypted_data_reader.close()
    hashed_data = md5.new(encrypted_data).digest()

    # there will be more or less redundancy depending on the audio duration and the data length
    bytes_pattern = 4
    bytes_data = os.path.getsize(tmp_data_encrypted)
    bytes_hash = 16
    bytes_total = bytes_pattern + bytes_data + bytes_hash

    # redundancy of data = maximum amount of data / total bytes to hide (integer)
    # maximum amount of data = bits per second of the new signal * seconds of audio
    # seconds of audio = total number of audio frames / framerate
    # bits per second = 1 / (samples per bit of signal / sample rate of audio)
    bits_per_second = 1 / (441.0 / 44100)
    seconds_of_audio = wave.open(tmp_audio_extracted).getnframes() / (wave.open(tmp_audio_extracted).getframerate() + 0.0)
    max_data = bits_per_second * seconds_of_audio
    redundancy = int(max_data / bytes_total)

    # data is written as much as possible
    if redundancy == 0:
        print_error('could not hide "' + input_file + '" inside "' + video_container  + '" due to size restrictions, please try again using a larger video or a smaller input file')
        exit(1)
    else:
        formatted_data_writer = open(tmp_data_formatted, 'w')
        for i in range(redundancy):
            formatted_data_writer.write(pattern + encrypted_data + hashed_data)
        formatted_data_writer.close()

# data retrieval function
def data_retrieval():

    # the obtained data consists in a loop of (specific pattern + encrypted data + md5 hash), the pattern has to be found in order to extract and check the encrypted data
    pattern = '\xde\xad\xbe\xef'
    formatted_data_reader = open(tmp_data_formatted, 'r')
    formatted_data = formatted_data_reader.read()
    formatted_data_reader.close()

    # get bits from extracted bytes
    formatted_data_string = ''
    for byte in formatted_data:
        if byte == '\x00':
            formatted_data_string += '0'
        else: # byte == '\x01'
            formatted_data_string += '1'

    # extract data between patterns
    pattern_binary = ''
    for byte in pattern:
        pattern_binary += bin(ord(byte))[2:].zfill(8)
    data_patterns = filter(None, formatted_data_string.split(pattern_binary))

    # integrity check
    failure = True
    for element in data_patterns:
        hashed_data = hex(int(element, 2))[2:-1].decode('hex')[-16:]
        encrypted_data = hex(int(element, 2))[2:-1].decode('hex')[:-16]
        if md5.new(encrypted_data).digest() == hashed_data:
            failure = False
            encrypted_data_writer = open(tmp_data_encrypted, 'w')
            encrypted_data_writer.write(encrypted_data)
            encrypted_data_writer.close()
            break
    if failure:
        print_error('encrypted data could not be retrieved intact from the audio in "' + video_container + '", seems like the video has been compressed or distorted (using a larger video or a smaller input file when encoding could help)')
        exit(1)

# definition of gnuradio flow blocks for the main encoding process
class encoding_top_block(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, 'Top Block')

        # sample frequency = 44100 Hz
        # 44100 discrete samples per second to reconstruct the signal when playing it back
        self.samp_rate = samp_rate = 44100

        # data to hide centered at (44100 / 2 - 1000) = 21050 Hz
        # human ear can't catch sounds below 20 Hz or above 20 kHz (however regular audio players won't reproduce sounds at 21050 Hz)
        self.freq_xlating_fir_filter_xxx_0 = gnufilter.freq_xlating_fir_filter_ccc(1, (1, ), samp_rate / 2 - 1000, samp_rate)
        
        # one encoded bit each (44100 / 100) samples of audio
        self.digital_gfsk_mod_0 = digital.gfsk_mod(
        	samples_per_symbol = samp_rate / 100,
        	sensitivity = 0.01,
        	bt = 0.35,
        	verbose = False,
        	log = False,
        )

        # block that defines the source audio file
        self.blocks_wavfile_source_0 = blocks.wavfile_source(tmp_audio_extracted, False)

        # block that defines the destination audio file
        self.blocks_wavfile_sink_0 = blocks.wavfile_sink(tmp_audio_modified, 1, samp_rate, 16)

        # block that defines the source data file to hide
        self.blocks_file_source_0 = blocks.file_source(gr.sizeof_char * 1, tmp_data_formatted, True)

        # block that defines sample rate when processing the audio
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_float * 1, samp_rate, True)

        # block that reduces the amplitude of both waves to half, avoiding any possible distorsion coming from wave overlapping
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_vff((.5, ))

        # block that transforms the complex gmsk signal to a real one so that it can be embedded into a wav file
        self.blocks_complex_to_real_0 = blocks.complex_to_real(1)

        # block that adds the original audio wave and the forged one
        self.blocks_add_xx_0 = blocks.add_vff(1)

        # connections between blocks
        self.connect((self.blocks_add_xx_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_complex_to_real_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_file_source_0, 0), (self.digital_gfsk_mod_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_wavfile_sink_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.blocks_wavfile_source_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.digital_gfsk_mod_0, 0), (self.freq_xlating_fir_filter_xxx_0, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.blocks_complex_to_real_0, 0))

# definition of gnuradio flow blocks for the main decoding process
class decoding_top_block(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, 'Top Block')

        # sample frequency = 44100 Hz (already explained)
        self.samp_rate = samp_rate = 44100

        # block that removes audio signal far from the selected frequency to avoid noise
        self.low_pass_filter_0 = gnufilter.fir_filter_ccf(1, firdes.low_pass(1, samp_rate, 200, 10, firdes.WIN_HANN, 6.76))

        # data to hide centered at (44100 / 2 - 1000) = 21050 Hz (already explained)
        self.freq_xlating_fir_filter_xxx_0_0 = gnufilter.freq_xlating_fir_filter_fcf(1, (1, ), - (samp_rate / 2 - 1000), samp_rate)

        # one encoded bit each (44100 / 100) samples of audio
        self.digital_gmsk_demod_0 = digital.gmsk_demod(
                samples_per_symbol = samp_rate / 100,
                gain_mu = 0.175,
                mu = 0.5,
                omega_relative_limit = 0.01,
                freq_error = 0.0,
                verbose = False,
                log = False,
        )
 
        # block that defines the source audio file
        self.blocks_wavfile_source_0 = blocks.wavfile_source(tmp_audio_extracted, False)

        # block that defines the destination data file to extract
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_char * 1, tmp_data_formatted, False)

        # block that defines the file writing as unbuffered to write to disk as soon as possible
        self.blocks_file_sink_0.set_unbuffered(True)

        # connections between blocks
        self.connect((self.blocks_wavfile_source_0, 0), (self.freq_xlating_fir_filter_xxx_0_0, 0))
        self.connect((self.digital_gmsk_demod_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0_0, 0), (self.low_pass_filter_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.digital_gmsk_demod_0, 0))

# audio replacing function
def replace_video_audio():

    # the new .wav file is converted to .mp3 without the polyphase lowpass filter, preventing the encoder from removing ultrasonic frequencies 
    ret = os.system('lame ' + tmp_audio_modified + ' --preset insane --lowpass -1 ' + tmp_audio_converted + ' > /dev/null 2>&1')
    if ret != 0:
        print_error('unexpected error while forging the .mp3 audio for the modified video, please try again or consider using a different video file from "' + video_container + '"')
        exit(1)

    # the modified .mp4 video is generated making use of the previous .mp3 audio
    ret = os.system('ffmpeg -i ' + video_container + ' -i ' + tmp_audio_converted + ' -codec copy -map 0:v -map 1:a -c:v copy -c:a copy ' + tmp_video_result + ' -y > /dev/null 2>&1')
    if ret != 0:
        print_error('unexpected error while forging the modified .mp4 video, please try again or consider using a different video file from "' + video_container + '"')
        exit(1)
    else:
        print_success('the new video file containing the data in "' + input_file + '" is located at "' + tmp_video_result + '"')
        exit(0)

# main method
def main():
    dependencies_check()
    arguments_check()
    extract_video_audio()
    if sys.argv[1] == 'encode':
        aes_encryption()
        data_format()
        main_encoding_process = encoding_top_block()
        print_info('signal modulation has started, please wait ...')
        main_encoding_process.start()
        main_encoding_process.wait()
        replace_video_audio()
    else: # sys.argv[1] == 'decode'
        main_decoding_process = decoding_top_block()
        print_info('signal demodulation has started, please wait ...')
        main_decoding_process.start()
        main_decoding_process.wait()
        data_retrieval()
        aes_decryption()

if __name__ == '__main__':
    main()
