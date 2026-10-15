# AI Inquiry Manager

A small local Flask dashboard for tracking customer messages. It uses SQLite, rule-based categories, and reply templates, so it works without an AI API or paid service.

## Requirements

- Python 3.10 or newer
- VS Code (recommended) with the Python extension

## Install and run on Windows

Open this project folder in VS Code, then open **Terminal → New Terminal**. Run these commands from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks virtual-environment activation, use Command Prompt in VS Code and run:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

Open the local URL printed in the terminal, normally http://127.0.0.1:5000. The app binds to this computer only and runs with Flask's debugger disabled. Keep the terminal running while using the app; press **Ctrl+C** to stop it.

## Test the application

Run the automated checks from the VS Code terminal:

```powershell
python -m unittest discover -s tests -v
```

1. Start the app and confirm the inbox contains four sample messages across the available categories.
2. Add a message such as “My package is late and I need tracking help.” Set its priority to **High** and add it. It should appear in the inbox under **Order issue**.
3. Try “I'm disappointed that the item arrived damaged.” It should be categorized as **Complaint**. Ask a question about price or availability to test **Inquiry**; a message with no matching terms will be **Other**.
4. Use the category selector on a message to correct its category, then choose **Save category**. The correction is stored in SQLite.
5. Update a message's status to **In progress** or **Resolved** and confirm it persists after reloading.
6. Filter the inbox by category, priority, status, or any combination. Choose **Clear filters** to restore the full inbox.
7. Choose **Generate suggested reply** on a message. The generated text appears in an editable draft area.
8. Edit the draft and choose **Save reviewed draft**. Confirm the changed text remains after reloading the page. The application does not send messages; drafts require human review before being used.
9. Try submitting the form without a name or message to see validation feedback.

Messages are stored in `instance/inquiries.db` and persist across restarts. Delete that database file while the app is stopped if you want to reset the app and reseed the examples.

## Notes

- Categories are assigned from message keywords in `app.py` and can be corrected; priority is selected when a message is added.
- Message statuses default to **New**. Existing databases receive the status column automatically, with current messages set to **New**.
- This is a local development MVP. Do not expose the Flask development server to the public internet or use it for sensitive customer data without adding production security and deployment configuration.
