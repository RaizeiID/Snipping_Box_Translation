from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V1_IDN', model_label='ORTCore V1 IDN', default_interval=180, extra_env={'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1', 'TITAN_IDN_LEVEL': 'MAX'}))


if __name__ == '__main__':
    main()
