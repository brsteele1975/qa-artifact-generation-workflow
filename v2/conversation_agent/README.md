Run python conversation_agent.py --help

## Usage

### CLI flags

| Long flag     | Short alias |
|---------------|-------------|
| `--mode`      | `-m`        |
| `--prd`       | `-p`        |
| `--message`   | `-msg`      |
| `--artifacts` | `-a`        |

### Make commands

| Command                              | What it does                        |
|--------------------------------------|-------------------------------------|
| `make gen PRD=path/to/prd.md`        | Run generation mode on a PRD file   |
| `make review MSG="..." ARTIFACTS=path/to/artifacts.json` | Run review mode   |
| `make test`                          | Run all 16 tests                    |
| `make help`                          | Show usage reference                |

### Quick start

    cp .env.example .env       # add your OPENAI_API_KEY
    pip install -r requirements.txt
    make gen PRD=sample_input/sample_prd.md
