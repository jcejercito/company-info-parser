# Company Info Parser

A Python-based tool for parsing, processing, and analyzing company information from Excel and JSON files. This project is designed to extract, transform, and organize company data for further analysis or reporting.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Input/Output](#inputoutput)
- [Testing](#testing)
- [Dependencies](#dependencies)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Program Flow](#program-flow)
- [Contact](#contact)

## Features

- Parses company information from Excel files (`CompanyInfo.xlsx`)
- Processes and aggregates data from multiple JSON files (in `backup/`)
- Saves processed links and data in `savedlinks/`
- Error logging via `crash-log.txt`
- Easily extensible for new data sources or formats

## Project Structure

```
.
├── CompanyInfo.xlsx         # Main Excel file with company data
├── crash-log.txt           # Log file for errors and crashes
├── MainParser.py           # Main Python script for parsing and processing
├── MainParser.spec         # PyInstaller spec file for building executables
├── backup/                 # Backup JSON files for each company/location
├── build/                  # Build artifacts (auto-generated)
├── savedlinks/             # Directory for storing processed links/data
└── tests/                  # Unit and integration tests
```

## Installation

1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd <repo-directory>
   ```

2. **(Optional) Create and activate a virtual environment:**
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
   > If `requirements.txt` is missing, install core dependencies manually:
   ```sh
   pip install pandas openpyxl
   ```

## Usage

1. **Prepare your input files:**
   - Place your main Excel file as `CompanyInfo.xlsx` in the project root.
   - Ensure all relevant JSON files are in the `backup/` directory.

2. **Run the parser:**
   ```sh
   python MainParser.py
   ```

3. **Check outputs:**
   - Processed data and links will be saved in the `savedlinks/` directory.
   - Any errors will be logged in `crash-log.txt`.

## Input/Output

- **Input:**
  - `CompanyInfo.xlsx`: Excel file with company information (columns: TODO: describe columns)
  - `backup/*.json`: JSON files for each company/location (structure: TODO: describe structure)

- **Output:**
  - Processed data files in `savedlinks/`
  - Error logs in `crash-log.txt`

## Testing

To run all tests:

```sh
python -m unittest discover tests
```

Or use your preferred test runner.

## Dependencies

- Python 3.8+
- pandas
- openpyxl
- (Other dependencies as required by your code)

## Troubleshooting

- **Missing modules:** Install dependencies as described above.
- **Excel/JSON parsing errors:** Check the format and integrity of your input files.
- **Permission errors:** Ensure you have read/write access to the project directories.

## License

This project is licensed under the [MIT License](LICENSE).

## Program Flow

1. **Initialization**  
   The program starts by setting up required modules, reading the main Excel file (`CompanyInfo.xlsx`), and preparing logging for errors.

2. **Region and City Traversal**  
   - The parser visits each region and city, either by reading from the web or from cached data.
   - For each city, it attempts to gather company information, handling pagination as needed.

3. **Caching Mechanism**  
   - To improve efficiency and support resuming interrupted sessions, the parser uses a caching system.
   - After processing a city or region, progress and collected data are saved as JSON files in the [`savedlinks/`](savedlinks/) directory.
   - If the program is restarted, it can pick up from the last saved state using these cache files, reducing redundant network requests.

4. **Company Data Extraction**  
   - For each company found, the parser extracts details such as name, address, telephone, fax, email, and website.
   - Data is temporarily stored in memory and then appended to the main Excel file.

5. **Error Handling**  
   - Any errors encountered during parsing or network requests are logged to [`crash-log.txt`](crash-log.txt).
   - The program is designed to retry on certain connection errors and to log tracebacks for unexpected issues.

6. **Output**  
   - Processed company data is appended to [`CompanyInfo.xlsx`](CompanyInfo.xlsx).
   - Cached progress and company links are stored in [`savedlinks/`](savedlinks/).

---

**Note:**  
The caching system ensures that if the script is interrupted or encounters an error, you can safely rerun it without losing progress or duplicating work. This is especially useful for large datasets or unstable network conditions.