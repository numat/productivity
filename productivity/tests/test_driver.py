import pytest

from productivity.mock import ProductivityPLC


@pytest.fixture
def plc_driver():
    return ProductivityPLC('fake ip', 'tests/plc_tags.csv')


def test_init():
    with pytest.raises(TypeError, match='unsupported data type'):
        ProductivityPLC('fake ip', 'tests/bad_tags.csv')


def test_get_tags(plc_driver):
    expected = {
        'AV-101': {'address': {'start': 1, 'end': 1}, 'id': 'DO-0.1.3.1',
                   'comment': 'Inert valve', 'type': 'bool'},
        'toggle_AV-101': {'address': {'start': 4, 'end': 4}, 'id': 'C-000048',
                          'type': 'bool'},
        'toggle_AV-102': {'address': {'start': 5, 'end': 5}, 'id': 'C-000049',
                          'type': 'bool'},
        'AV-102': {'address': {'start': 6, 'end': 6}, 'id': 'DO-0.1.3.6',
                   'comment': 'Gas valve', 'type': 'bool'},
        'FALL-101_OK': {'address': {'start': 6, 'end': 6}, 'id': 'C-000050',
                        'comment': 'Low-low beer flow shutdown', 'type': 'bool'},
        'FAL-101_OK': {'address': {'start': 7, 'end': 7}, 'id': 'C-000051',
                       'comment': 'Low beer flow warning', 'type': 'bool'},
        'ESD_OK': {'address': {'start': 9, 'end': 9}, 'id': 'C-000003',
                   'comment': 'Emergency shutdown triggered', 'type': 'bool'},
        'FI-101': {'address': {'start': 400001, 'end': 400002}, 'id': 'F32-000003',
                   'comment': 'Source gas transducer', 'type': 'float'},
        'FI-102': {'address': {'start': 400003, 'end': 400004}, 'id': 'F32-000006',
                   'comment': 'Sample cell transducer', 'type': 'float'},
        'FIC-101_SP': {'address': {'start': 400005, 'end': 400005}, 'id': 'F32-000009',
                       'comment': 'Source gas pressure setpoint', 'type': 'float'},
        'FIC-102_SP': {'address': {'start': 400005, 'end': 400005}, 'id': 'F32-000012',
                       'comment': 'Sample cell pressure setpoint', 'type': 'float'},
        'GAS-101': {'address': {'start': 400019, 'end': 400022}, 'id': 'STR-000001',
                    'comment': 'Acid gas', 'length': 8, 'type': 'str'},
        'GAS-102': {'address': {'start': 400023, 'end': 400026}, 'id': 'STR-000002',
                    'comment': 'Base gas', 'length': 8, 'type': 'str'},
        'Raw Pressure': {'address': {'end': 400028, 'start': 400027}, 'type': 'int32',
                         'comment': 'Analog Pressure', 'id': 'AIS32-000001'},
    }
    assert plc_driver.get_tags() == expected


@pytest.mark.asyncio
async def test_get(plc_driver):
    expected = {'AV-101': False, 'toggle_AV-101': False, 'toggle_AV-102': False,
                'FALL-101_OK': False, 'FAL-101_OK': False, 'ESD_OK': False,
                'FI-101': 0.0, 'FI-102': 0.0, 'FIC-102_SP': 0.0, 'Raw Pressure': 0,
                'GAS-101': '\x00\x00\x00\x00\x00\x00\x00\x00',
                'GAS-102': '\x00\x00\x00\x00\x00\x00\x00\x00'}
    assert await plc_driver.get() == expected

@pytest.mark.asyncio
async def test_roundtrip(plc_driver):
    await plc_driver.set({'AV-101': True, 'toggle_AV-101': True, 'Raw Pressure': 1,
                          'FI-101': 20.0, 'GAS-101': 'FOO'})
    expected = {'AV-101': True, 'toggle_AV-101': True, 'toggle_AV-102': False,
                'FALL-101_OK': False, 'FAL-101_OK': False, 'ESD_OK': False,
                'FI-101': 20.0, 'FI-102': 0.0, 'FIC-102_SP': 0.0, 'Raw Pressure': 1,
                'GAS-101': 'FOO     ', 'GAS-102': '\x00\x00\x00\x00\x00\x00\x00\x00'}
    assert await plc_driver.get() == expected


@pytest.mark.asyncio
async def test_set_errors(plc_driver):
    with pytest.raises(TypeError, match='Invalid input'):
        await plc_driver.set('FOO')
    with pytest.raises(TypeError, match='Invalid input'):
        await plc_driver.set({}, True)
    with pytest.raises(TypeError, match='No settings provided'):
        await plc_driver.set()
    with pytest.raises(ValueError, match='missing the following tags'):
        await plc_driver.set(av101=True)


@pytest.mark.asyncio
async def test_type_checking(plc_driver):
    with pytest.raises(ValueError, match='Expected AV-101 to be a bool'):
        await plc_driver.set({'AV-101': 1})
    with pytest.raises(ValueError, match='Expected toggle_AV-101 to be a bool'):
        await plc_driver.set({'toggle_AV-101': 1})
    with pytest.raises(ValueError, match='Expected FI-101 to be a float'):
        await plc_driver.set({'FI-101': 'FOO'})
    with pytest.raises(ValueError, match='Expected GAS-101 to be a str'):
        await plc_driver.set({'GAS-101': 1})
