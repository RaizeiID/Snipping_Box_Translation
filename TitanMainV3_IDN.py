from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V3_IDN', model_label='ORTCore V3 IDN', default_interval=300, extra_env={'TITAN_ACCURACY_FIRST': '1', 'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1'}))


if __name__ == '__main__':
    main()
