import argparse
from pathlib import Path
import uvicorn
from .app import create_app
from .config import load_config


def main():
    parser = argparse.ArgumentParser(description="MCT431 gateway; run from the repository root")
    parser.add_argument("--config", default="config/local.toml" if Path("config/local.toml").exists() else "config/design.toml")
    parser.add_argument("--simulate", action="store_true", help="use diagnostic software stations, not physical boards")
    args = parser.parse_args()
    config = load_config(args.config)
    app = create_app(config, args.simulate)
    uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"], workers=1)


if __name__ == "__main__":
    main()
