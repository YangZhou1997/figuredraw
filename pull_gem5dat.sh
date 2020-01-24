# !/bin/bash

node0=clnode129.clemson.cloudlab.us
node1=clnode131.clemson.cloudlab.us
node2=clnode165.clemson.cloudlab.us
node3=clnode179.clemson.cloudlab.us
node4=clnode122.clemson.cloudlab.us
node5=clnode113.clemson.cloudlab.us

m5out_dir=/users/yangzhou/gem5/sgx_nic/m5out/*
stdout_dir=/users/yangzhou/gem5/sgx_nic/results/*
stderr_dir=/users/yangzhou/gem5/sgx_nic/stderr/*
scriptgen_dir=/users/yangzhou/gem5/sgx_nic/scriptgen/*

datadir=gem5data

mkdir -p ./$datadir/m5out/
mkdir -p ./$datadir/results/
mkdir -p ./$datadir/stderr/
mkdir -p ./$datadir/scriptgen/

for node in $node0 $node1 $node2 $node3
do
    rsync -auv -e ssh yangzhou@$node:$m5out_dir ./$datadir/m5out/
    rsync -auv -e ssh yangzhou@$node:$stdout_dir ./$datadir/results/
    rsync -auv -e ssh yangzhou@$node:$stderr_dir ./$datadir/stderr/
    rsync -auv -e ssh yangzhou@$node:$scriptgen_dir ./$datadir/scriptgen/
done