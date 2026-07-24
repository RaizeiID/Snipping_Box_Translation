from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V4', model_label='ORTCore V4', default_interval=220, extra_env={'TITAN_HYBRID': '1'}))


if __name__ == '__main__':
    main()
