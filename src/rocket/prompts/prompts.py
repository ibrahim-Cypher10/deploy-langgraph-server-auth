import os
import glob


def load_prompts():
    """
    Reads all .txt files in the prompts directory and loads them into variables
    with the same name as the files without the .txt extension.

    Returns:
        dict: A dictionary where keys are variable names (filename without .txt)
              and values are the file contents as strings.
    """
    # Get the directory where this file is located
    prompts_dir = os.path.dirname(os.path.abspath(__file__))

    # Find all .txt files in the prompts directory
    txt_files = glob.glob(os.path.join(prompts_dir, "*.txt"))

    prompts = {}

    for file_path in txt_files:
        # Get the filename without path and extension
        filename = os.path.basename(file_path)
        variable_name = os.path.splitext(filename)[0]

        # Read the file content
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                prompts[variable_name] = content
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            prompts[variable_name] = None

    return prompts


# Load all prompts when the module is imported
_loaded_prompts = load_prompts()

# Create module-level variables for each prompt
for _prompt_name, _prompt_content in _loaded_prompts.items():
    globals()[_prompt_name] = _prompt_content