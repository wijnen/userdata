all: test.elf

CXXFLAGS = -Wall -Wextra -Werror -std=c++23 -I../../../webloop/include -ggdb3
#CXXFLAGS = -std=c++23 `pkgconf --cflags webloop`
LDFLAGS = -std=c++23 -ggdb3
LIBADD = -L../../../webloop/.libs -lwebloop #`pkgconf --libs webloop`

%.o: %.cc userdata.hh Makefile
	g++ ${CPPFLAGS} ${CXXFLAGS} -o $@ -c $<

%.elf: %.o Makefile
	g++ ${LDFLAGS} $< -o $@ ${LIBADD}

test: test.elf
	LD_LIBRARY_PATH=../../../webloop/.libs ./test.elf --allow-local

clean:
	rm *.o *.elf
