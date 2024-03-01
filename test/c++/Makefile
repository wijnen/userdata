all: test.elf

WEBLOOPDIR = ../../../webloop/include
WEBLOOPFILES = coroutine.hh fhs.hh loop.hh network.hh tools.hh url.hh webobject.hh websocketd.hh

CXXFLAGS = -Wall -Wextra -fstack-protector-strong -D_FORTIFY_SOURCE=3 -Werror -std=c++23 -I${WEBLOOPDIR} -ggdb3
#CXXFLAGS = -std=c++23 `pkgconf --cflags webloop`
LDFLAGS = -std=c++23 -ggdb3
LIBADD = -L../../../webloop/.libs -lwebloop #`pkgconf --libs webloop`

DEPS = Makefile userdata.hh $(addprefix ${WEBLOOPDIR}/webloop/,${WEBLOOPFILES})

%.o: %.cc ${DEPS}
	g++ ${CPPFLAGS} ${CXXFLAGS} -o $@ -c $<

%.elf: %.o Makefile
	g++ ${LDFLAGS} $< -o $@ ${LIBADD}

test: test.elf
	LD_LIBRARY_PATH=../../../webloop/.libs ./test.elf ${ARGS}

valgrind: test.elf
	LD_LIBRARY_PATH=../../../webloop/.libs valgrind --xtree-memory=full --read-var-info=yes --track-origins=yes --vgdb=full --vgdb-error=0 ./test.elf ${ARGS}

clean:
	rm *.o *.elf

.PHONY: test valgrind clean
