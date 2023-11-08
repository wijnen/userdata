all: test.elf

CXXFLAGS = -std=c++23 `pkgconf --cflags webloop`
LDFLAGS = `pkgconf --ldflags webloop`
LIBADD = `pkgconf --libs webloop`

%.o: %.cc userdata.hh Makefile
	g++ ${CPPFLAGS} ${CXXFLAGS} -o $@ -c $<

%.elf: %.o Makefile
	g++ ${LDFLAGS} $< -o $@ ${LIBADD}
