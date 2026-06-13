#!/usr/bin/env bash

{
    echo "=================================================="
    echo "EXPERIMENTS"
    echo "=================================================="
    tree experiments

    echo
    echo
    echo "=================================================="
    echo "EXPERIMENTS-V01"
    echo "=================================================="
    tree experiments-v01
} > comparison-tree.txt
