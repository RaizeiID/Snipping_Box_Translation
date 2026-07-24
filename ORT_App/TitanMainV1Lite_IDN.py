from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V1L_IDN', model_label='ORTCore V1 Lite IDN', default_interval=200, extra_env={'TITAN_LITE': '1', 'TITAN_LITE_NAME_ONLY': '1', 'TITAN_USE_LITE_POLICY': '1', 'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1', 'TITAN_IDN_LEVEL': 'MAX'}))


if __name__ == '__main__':
    main()
