from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V4_IDN', model_label='ORTCore V4 IDN', default_interval=220, extra_env={'TITAN_HYBRID': '1', 'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1'}))


if __name__ == '__main__':
    main()
