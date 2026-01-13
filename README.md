# Multi-Source Downloader

A desktop application for downloading and processing data from multiple sources with standard number completion functionality.

## Features

- Multi-source data retrieval and search
- Standard number completion and supplementation
- Excel file processing and batch operations
- Desktop UI with intuitive interface
- Cross-platform support (Windows 7+)
- Built with PySide for modern UI experience

## System Requirements

- **Windows 7 or later**
- **.NET Framework** (for some dependencies)
- **Internet connection** for API calls

## Installation & Usage

### Option 1: Pre-compiled Executable (Recommended)

Download the latest executable from the releases page and run directly - no installation required.

### Option 2: From Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/atpx4869/Multi-source-downloader.git
   cd Multi-source-downloader
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python desktop_app.py
   ```

## Configuration

### API Configuration

Edit `config/api_config.json` to configure API endpoints and credentials:

```json
{
  "api_name": {
    "enabled": true,
    "base_url": "https://api.example.com",
    "timeout": 30
  }
}
```

Refer to `config/API_CONFIG_GUIDE.md` for detailed configuration instructions.

## Features Overview

### 1. Data Search & Download
- Multi-source search with unified interface
- Batch download support
- Progress tracking and error handling

### 2. Standard Number Processing
- Automatic detection of incomplete standard numbers
- Query and completion from authoritative databases
- Batch Excel file processing
- Export results to Excel/CSV formats

### 3. User Interface
- Clean, responsive desktop application
- Real-time processing feedback
- Customizable settings
- Built-in file browser

## Project Structure

```
├── api/                      # API adapters for different sources
├── app/                      # Desktop application UI
├── config/                   # Configuration files
├── core/                     # Core business logic
├── sources/                  # Data source implementations
├── web_app/                  # Web utilities and processors
├── docs/                     # Documentation
├── examples/                 # Usage examples
└── README.md                 # This file
```

## Development

### Building Executable

Using PyInstaller:
```bash
python -m PyInstaller --onefile --windowed --icon=app/icon.ico --name=MultiSourceDownloader desktop_app.py
```

Using Nuitka (faster, native compilation):
```bash
python -m nuitka --onefile --standalone --enable-plugin=pyside6 --windows-icon-from-ico=app/icon.ico desktop_app.py
```

### Testing

Run the application with debug mode to see detailed logs.

## Performance

- **Standard number batch processing:** ~100-200 items/minute
- **Search operation:** ~0.3-0.5 seconds per query
- **Startup time:** ~2-3 seconds

## Troubleshooting

### Common Issues

1. **"API connection timeout"**
   - Check internet connection
   - Verify API endpoints in config file
   - Increase timeout value in configuration

2. **"Cannot find standard"**
   - Verify standard number format is correct
   - Check if standard number exists in sources
   - Try alternative search sources

3. **Excel processing errors**
   - Ensure Excel file is not corrupted
   - Check file permissions
   - Try closing the file in other applications first

## Documentation

- [API Architecture](docs/api/API_ARCHITECTURE.md)
- [Local Run Guide](docs/guides/LOCAL_RUN_GUIDE.md)
- [Performance Optimization](docs/guides/PERFORMANCE_OPTIMIZATION.md)
- [Project Structure](docs/guides/PROJECT_STRUCTURE.md)

## License

This project is provided as-is for personal and internal use.

## Support

For issues, questions, or suggestions, please refer to the documentation or check the project's issue tracker.

---

**Version:** 4.0  
**Last Updated:** January 2026
