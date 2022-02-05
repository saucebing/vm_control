cd /root/parsec-3.0
source /root/parsec-3.0/env.sh
thread=$1
input=$3
benchmark=$2
index=$5
#benchmark='splash2x.raytrace'
#splash2x.raytrace
#parsec.x264
#parsec.raytrace
#parsec.streamcluster 
#parsec.fluidanimate
#parsec.blackscholes
#parsec.bodytrack
#parsec.canneal
#parsec.freqmine
#parsec.ferret
#parsec.netstreamcluster
#parsec.netferret
#splash2x.water_spatial
#splash2x.water_nsquared
#splash2x.lu_ncb
#splash2x.lu_cb
#splash2x.barnes

rm -rf result/run$index
mkdir -p result/run$index
for i in `seq $4`
do
    parsecmgmt -a run -p $benchmark -i $input -n $thread -d result/run$index
done
#parsecmgmt -a run -p $benchmark -i $input -n $thread
#for i in `seq 1`
#do
#    parsecmgmt -a run -p $benchmark -i $input -n $thread
#done
