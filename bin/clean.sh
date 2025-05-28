#!/bin/bash

current_dir=$(pwd)
target_dir="vidSumm/bin"
if [[ "$current_dir" == */$target_dir ]]; then
  cd ..
fi

if [ "$(ls -A audio)" ]; then
    rm -r audio/*
fi

if [ "$(ls -A video)" ]; then
    rm -r video/*
fi

if [ "$(ls -A lecture_notes)" ]; then
    rm -r lecture_notes/*
fi

rm transcript.txt
rm notes.txt
rm flashcards.json

# if [ "$(ls -A topic_clips)" ]; then
#     rm -r topic_clips/*
# fi

# for folder in output/*; do
#     if [ -d "$folder/clips" ]; then
#         rm -r "$folder/clips"
#     fi
#     if [ -d "$folder/spedup" ]; then
#         rm -r "$folder/spedup"
#     fi
#     if [ -d "$folder/transcripts" ]; then
#         rm -r "$folder/transcripts"
#     fi
#     if [ -f "$folder/file_list.txt" ]; then
#         rm "$folder/file_list.txt"
#     fi
# done

# # Check if --remove-output flag is set
# for arg in "$@"
# do
#     if [ "$arg" == "--remove-output" ]; then
#         rm -r output/*
#     elif [ "$arg" == "--remove-transcript" ]; then
#         if [ "$(ls -A transcript)" ]; then
#             rm -r transcript/*
#         fi
#     fi
# done