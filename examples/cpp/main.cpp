
#include <cstdio>
#include <thread>
#include <chrono>
#include <vector>
extern char **environ;

void spawn_threads(int count) {
	std::vector<std::thread> threads;
	for (int i = 0; i < count; i++) {
		threads.emplace_back(([=]{
			pthread_setname_np(("Thread " + std::to_string(i)).c_str());
			int timeout = i * 1000 + 500;
			printf("from thread sleep %d\n", timeout);
			std::this_thread::sleep_for(std::chrono::milliseconds(timeout));
		}));
	}
	for (auto& thread : threads) {
		thread.join();
	}
}

void test() {
	for (int i = 0; i < 25; i++)
		fprintf(stderr, "abcdefghijklmopqrstuvwxyz\n");
}

int main(int argc, char ** argv) {
	char **vars = environ;
	while (*vars) {
		printf("%s\n", *vars);
		vars += 1;
	}

	test(); 
	spawn_threads(5);
	return 1;
}
