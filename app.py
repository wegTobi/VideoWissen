"""Startpunkt der Desktop-Anwendung und optionaler lokaler Paket-Selbsttest."""
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VideoWissen")
    parser.add_argument("--self-test", type=str, metavar="REPORT")
    parser.add_argument("--model", type=str)
    parser.add_argument("--audio", type=str)
    parser.add_argument("--download-model", type=str)
    args = parser.parse_args()
    if args.self_test:
        from video_assistant.diagnostics import run_self_test
        raise SystemExit(run_self_test(args.self_test, args.model, args.audio, args.download_model))
    from video_assistant.gui import main
    main()

