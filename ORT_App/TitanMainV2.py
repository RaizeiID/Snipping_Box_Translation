from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V2', model_label='ORTCore V2', default_interval=220, extra_env={}))


if __name__ == '__main__':
    main()
