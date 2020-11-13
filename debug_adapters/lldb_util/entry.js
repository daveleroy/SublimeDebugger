// Modified from https://github.com/vadimcn/vscode-lldb/blob/master/extension/novsc/adapter.ts

const { spawn } = require('child_process');
const net = require('net');
const _fs = require('fs');
const _cp = require('child_process');
const { promisify } = require('util');


const async_readdir = promisify(_fs.readdir);
const async_readFile = promisify(_fs.readFile);
const async_exists = promisify(_fs.exists);
const async_stat = promisify(_fs.stat);
const async_execFile = promisify(_cp.execFile);


var client = null
var stdin_data_before_connection = ""

codelldb = process.argv[2]
proc = null

function cleanup() {
	proc.kill()
	process.exit(0)
}

process.on('exit', cleanup);
process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

process.stdin.on('readable', () => {
	let chunk;
	while ((chunk = process.stdin.read()) !== null) {
		if (client) {
			client.write(chunk)
		}
		else {
			stdin_data_before_connection += chunk
		}
	}
});

async function main() {
	proc = spawn(codelldb, [
	],
		{stdio: ['ignore', 'pipe', 'pipe']}
	);

	let port = await getDebugServerPort(proc)
	client = new net.Socket();

	// write all the stdin data that arrived before we connected
	client.connect(port, 'localhost', function() {
		client.write(stdin_data_before_connection)
	});

	client.on('data', function(data) {
		process.stdout.write(data)
	});

	client.on('close', function() {
	});
}; main()

async function getDebugServerPort(process) {
	let regex = /^Listening on port (\d+)\s/m;
	let match = await waitForPattern(process, process.stdout, regex);
	return parseInt(match[1]);
}

async function waitForPattern(process, channel, pattern, timeoutMillis = 10000) {
	return new Promise((resolve, reject) => {
		let promisePending = true;
		let processOutput = '';
		// Wait for expected pattern in channel.
		channel.on('data', chunk => {
			let chunkStr = chunk.toString();
			if (promisePending) {
				processOutput += chunkStr;
				let match = pattern.exec(processOutput);
				if (match) {
					clearTimeout(timer);
					processOutput = null;
					promisePending = false;
					resolve(match);
				}
			}
		});
		// On spawn error.
		process.on('error', err => {
			promisePending = false;
			reject(err);
		});
		// Bail if LLDB does not start within the specified timeout.
		let timer = setTimeout(() => {
			if (promisePending) {
				process.kill();
				let err = Error('The debugger did not start within the allotted time.');
				(err).code = 'Timeout';
				(err).stdout = processOutput;
				promisePending = false;
				reject(err);
			}
		}, timeoutMillis);
		// Premature exit.
		process.on('exit', (code, signal) => {
			if (promisePending) {
				let err = Error('The debugger exited without completing startup handshake.');
				(err).code = 'Handshake';
				(err).stdout = processOutput;
				promisePending = false;
				reject(err);
			}
		});
	});
}

async function findLibPython() {
	return async_execFile(codelldb, ['find-python'])
			.then(result => result.stdout.trim()).catch(_err => null)
}
