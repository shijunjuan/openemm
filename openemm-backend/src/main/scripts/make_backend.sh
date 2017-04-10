#!/bin/bash

export PATH=$PATH:$OE_HOME\bin:/cygdrive/c/git/openemm/openemm-backend/target/generated-sources/sa-1.2.6:/cygdrive/c/git/openemm/openemm-backend/target/generated-sources/slang-1.4.9

tar -xvzf sa-1.2.6.tar.gz
cd sa-1.2.6
./configure --prefix="/cygdrive/c/git/openemm/openemm-backend/target/build/bin" --disable-shared --build=arm-unknown-linux-gnu

make
make install
cd ..

#tar -xvzf slang-1.4.9.tar.gz
#cd slang-1.4.9
#./configure --prefix="$/cygdrive/c/git/openemm/openemm-backend/target/build/bin" --host=arm-unknown-linux-gnu
#make
#make install
#cd ..

cd "$SRC/src/c/lib"
make
cd "$SRC/src/c/tools"
make
cd "$SRC/src/c/xmlback"
make
cd "$SRC/src/c/bav"
make 