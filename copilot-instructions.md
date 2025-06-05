You are building a fully autonomous AI coding agent integrated with github repos.
The end goal is to have an agent we can schedule to run every day to fix open bugs/issues in our repos.

Use google gemini to integrate with AI models.
Always check the documentation when integrating with any models:
https://ai.google.dev/gemini-api/docs/text-generation
prefer model gemini-2.5-pro-preview-05-06 to gemini-2.5-flash-preview-05-20
Use the latest version of the model available.

If you come across a bad indentention, pause and let the user fix it.

IMPORTANT:
Always use the tools/replace_string_in_file.py script to replace strings in files.