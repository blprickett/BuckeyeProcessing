import numpy as np
import scipy.io.wavfile
import re
from math import floor
from os import listdir

#First, read in the demographic file to get each speaker's demo:
demo2speakers = {"fy":[], "my":[], "fo":[], "mo":[]}
speaker2demo = {}
demo_file = open("speaker_demos.txt", "r")
for line in demo_file.readlines():
    sp, g, a, _ = line.rstrip().split(" ")
    sp = re.sub("S", "", sp)
    demo = g+a
    demo2speakers[demo].append(sp)
    speaker2demo[sp] = demo
demo_file.close()

#These dictionaries will help us keep track of how many speakers we have
#in each split of the data:
split2demoCounts = {
                        "Train": {"fy":0, "my":0, "fo":0, "mo":0},
                        "Dev": {"fy":0, "my":0, "fo":0, "mo":0},
                        "Test": {"fy":0, "my":0, "fo":0, "mo":0}
                    }
split2speakers = {"Train":[], "Dev":[], "Test":[]}

#Now we'll loop through all of our speakers:
first_time = True
for speaker in speaker2demo.keys():
    #Add this speaker to our demo-based count used for splitting things up:
    split = "Train"
    demo = speaker2demo[speaker]
    if split2demoCounts["Train"][demo] == 6:
        split = "Dev"
        if split2demoCounts["Dev"][demo] == 2:
            split = "Test"
        elif split2demoCounts["Test"][demo] == 2:
            raise Exception(speaker)
    split2speakers[split].append(speaker)
    split2demoCounts[split][demo] += 1
    print(speaker, split)
    
    #Create/open the appropriate transcription output files:
    if first_time:
        orth_file = open(split+"/orthographic_data.txt", "w")
        transc_file = open(split+"/transcription_data.txt", "w") 
        first_time = False
    else:
        orth_file = open(split+"/orthographic_data.txt", "a")
        transc_file = open(split+"/transcription_data.txt", "a")
    
    #Get the transcription data filenames for this speaker:
    FN = listdir("Data/s"+speaker)
    files = []
    for fn in FN:
        fn_regex = re.search("s\d\d(\d\d.)\.words", fn)
        if fn_regex:
            files.append(fn_regex.group(1))

    #Process each of this speaker's files:
    for file in files:
        prev_end = 0
        print("\t"+file)
        text_f = open("Data/s"+speaker+"/s"+speaker+file+".words", "r")

        utt_texts = [] #Phonemic transcription associated with each utterance
        utt_orths = [] #Orthograpic transcription associated with each utterance
        utt_times = [] #[start time, end time] for each utterance

        #This code is a huge mess, but it should work.
        #It loops through the transcription files, saving timestamp information
        #for each of the utterances in the file.
        utt_i = -1
        new_utt = False
        new_file = True
        waiting_for_word = False
        for line in text_f.readlines():
            beg = re.search("([0-9.]+) +\d+ {B_TRANS};", line) #beginning of transc. file
            end = re.search("([0-9.]+) +\d+ {E_TRANS};", line) #end of transc. file
            not_word = re.search("([0-9.]+) +\d+ <(.+)>; (.); .; .+", line) #this matches any lines that aren't words
            word = re.search("([0-9.]+) +\d+ (.+); (.+); (.+); (.+)", line) #this matches any lines that are words
            comment = re.search("^[^ ]", line) #Their comments are just lines without any leading white space  

            if not_word:
                #Interviewer talking or silence will end the utterance:
                if re.search("IVER|SIL", not_word.group(2)): 
                    if waiting_for_word:
                        if utt_i > len(utt_times) - 1:
                            print("UI", utt_i)
                        if len(utt_times[utt_i]) < 2:
                            print(utt_times)
                        utt_times[utt_i][1] = float(prev_end)
                        prev_end = float(not_word.group(1))
                        continue
                    else:
                        if not new_file:
                            utt_times[utt_i][1] = float(prev_end)
                        utt_i += 1
                        utt_times.append([-1.0, -1.0])
                        utt_texts.append([])
                        utt_orths.append([])
                else:
                    if new_file:
                        utt_i += 1
                        utt_times.append([prev_end, -1.0])
                        utt_texts.append([])
                        utt_orths.append([])  
                        new_file = False
                    utt_texts[utt_i].append(not_word.group(3))
                    utt_orths[utt_i].append(not_word.group(2))
                waiting_for_word = True
                prev_end = float(not_word.group(1))
            elif beg:
                prev_end = float(beg.group(1))
            elif end:
                utt_times[utt_i][1] = float(end.group(1))
                continue
            elif line == "":
                continue
            elif comment:
                continue
            elif word:
                if new_file:
                        utt_i += 1
                        utt_times.append([prev_end, -1.0])
                        utt_texts.append([])
                        utt_orths.append([])                     
                new_file = False
                waiting_for_word = False
                
                #Get the word's start and end time:
                word_start = float(prev_end)
                word_end = float(word.group(1))
                
                #Start a new utterance if this one gets too long (>12 seconds)
                if (utt_times[utt_i][0] != -1) and ((word_end - utt_times[utt_i][0]) > 12):
                    utt_times[utt_i][1] = float(prev_end)
                    utt_i += 1
                    utt_times.append([word_start, -1.0])
                    utt_texts.append([])
                    utt_orths.append([])  

                prev_end = word_end            
                
                #Get other info:
                orth = word.group(2) #orthography of word
                dict_transc = word.group(3) #transcription of the word from a dictionary
                real_transc = word.group(4) #actual transciption from this recording
                pos = word.group(5) #part of speech
                
                if utt_times[utt_i][0] == -1:
                    utt_times[utt_i][0] = word_start
                    
                utt_texts[utt_i].append(real_transc) #save the phonemic transcription
                utt_orths[utt_i].append(orth) #save the orthographic transcription
        text_f.close()

        #Sometimes the messy code above produces an empty utterance at the start or end. 
        #Here we delete those:
        while utt_times[-1][0] == -1 or utt_times[-1][1] == -1 or utt_texts[-1] == "" or utt_orths[-1] == "":
            utt_times.pop()
            utt_texts.pop()
            utt_orths.pop()    
        while utt_times[0][0] == -1 or utt_times[0][1] == -1 or utt_texts[0] == "" or utt_orths[0] == "":
            utt_times.pop(0)
            utt_texts.pop(0)
            utt_orths.pop(0)

        #Now we loop through every utterance, creating a corresponding audio file,
        #and saving the transcription to our output file.
        for utt_i, startEnd in enumerate(utt_times):
            #Make a matching audio file for each utterance:    
            rate, data = scipy.io.wavfile.read("Data/s"+speaker+"/s"+speaker+file+'.wav')
            length = str(startEnd[1] - startEnd[0])
            if "-" in length:
                print(utt_times[utt_i-1])
                print(startEnd)
                print(utt_times[utt_i+1])
                raise Exception()
            if startEnd[1] < 0 or startEnd[0] < 0:
                print(utt_times)
                raise Exception(startEnd)
            new_data = data[floor(rate*startEnd[0]):floor(rate*startEnd[1])]
            scipy.io.wavfile.write(split+'/s'+speaker+file+'_Utt'+str(utt_i)+'.wav', rate, new_data)
            transc_file.write('s'+speaker+file+'_Utt'+str(utt_i)+"\t"+length+"\t"+" ".join(utt_texts[utt_i])+"\n")
            orth_file.write('s'+speaker+file+'_Utt'+str(utt_i)+"\t"+length+"\t"+" ".join(utt_orths[utt_i])+"\n")
    orth_file.close()
    transc_file.close()