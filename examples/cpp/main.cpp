
#include <stdio.h>
#include <thread>
#include <chrono>
#include <vector>

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
	fprintf(stderr, "printed from stderr");
	
}

int main(int argc, char ** argv) {
	test();
	spawn_threads(5);
	return 1;
}