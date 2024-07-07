import subprocess

def execute_shell_command(command):
    """
    Execute a shell command and return the output and error messages, if any.

    :param command: The shell command to execute as a string.
    :return: A tuple containing (output, error, return_code)
    """
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout, e.stderr, e.returncode

if __name__ == "__main__":
    json_val = "[{\"disc\": {\"block_size\": 21,\"path_to_file\": \"temp/temp_file.npy\"},\"function_input\": {\"output_size\": 21},\"memory\": {\"size_in_bytes\": 21},\"network\": {\"use\": false},\"workload\": {\"array_size\": 21,\"iterations\": 200000,\"operator\": \"*\",\"type\": \"float32\"},\"writeFile\": {\"block_size\": 21,\"path_to_file\": \"temp/temp_file.npy\"}}]"
    command = f"curl 172.17.0.3:9000 --request POST --data '{json_val}' --header 'Content-Type: application/json'"  # Example command
    output, error, return_code = execute_shell_command(command)

    print("Output:\n", output)
    print("Error:\n", error)
    print("Return Code:\n", return_code)
