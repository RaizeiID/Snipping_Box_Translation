from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V3L_IDN', model_label='ORTCore V3 Lite IDN', default_interval=320, extra_env={'TITAN_LITE': '1', 'TITAN_ACCURACY_FIRST': '1', 'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1'}))


if __name__ == '__main__':
    main()
