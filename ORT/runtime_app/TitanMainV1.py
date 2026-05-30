from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V1', model_label='ORTCore V1', default_interval=180, extra_env={}))


if __name__ == '__main__':
    main()
