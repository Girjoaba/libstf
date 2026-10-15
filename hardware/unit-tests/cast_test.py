import random
from typing import List, Tuple
from unit_test.fpga_stream import Stream, StreamType, get_bytes_for_stream_type
from libstf_utils.configured_test_case import ConfiguredTestCase
from libstf_utils.fpga_configuration import StreamConfig

# Number of 32-bit values per 512-bit input beat
VALUES_PER_BEAT = 16


def random_values(n: int) -> Stream:
    # Full 32-bit range, so wrong byte selection shows up in the truncated output
    return Stream(StreamType.UNSIGNED_INT_32, [random.randint(0, 2**32 - 1) for _ in range(n)])


def cast(values: Stream, out_type: StreamType) -> Stream:
    mask = (1 << (get_bytes_for_stream_type(out_type) * 8)) - 1
    return Stream(out_type, [v & mask for v in values.data])


class CastTest(ConfiguredTestCase):
    """
    These tests test the TypedNDataCast module. The input are 32-bit values, the output type is
    configured per transfer through the stream configuration.
    """

    debug_mode = True
    verbose_logging = True
    alternative_vfpga_top_file = "vfpga_tops/cast_test.sv"

    def setUp(self):
        super().setUp()
        self.transfers: List[Tuple[Stream, StreamType]] = None

    def configure(self):
        assert self.transfers is not None, "Cannot have cast test without transfers!"

        stream_config = self.config.get_config(StreamConfig)
        for (_, out_type) in self.transfers:
            stream_config.enqueue_stream_config(0, out_type)

        for (values, _) in self.transfers:
            self.set_stream_input(0, values)

        for (values, out_type) in self.transfers:
            self.set_expected_output(0, cast(values, out_type))

    def run_transfers(self, transfers: List[Tuple[Stream, StreamType]]):
        # Arrange
        self.transfers = transfers

        # Act
        self.simulate_fpga()

        # Assert
        self.assert_simulation_output()

    def test_16bit(self):
        """
        Several full output beats followed by a partial one.
        """
        self.run_transfers([
            (random_values(2 * 3 * VALUES_PER_BEAT + 5), StreamType.UNSIGNED_INT_16),
        ])

    def test_8bit_end_positions(self):
        """
        Transfers ending in every quarter of an output beat, with and without a partial last
        input beat, including an exactly full output beat.
        """
        self.run_transfers([
            (random_values(VALUES_PER_BEAT - 1), StreamType.UNSIGNED_INT_8),
            (random_values(2 * VALUES_PER_BEAT), StreamType.UNSIGNED_INT_8),
            (random_values(3 * VALUES_PER_BEAT - 7), StreamType.UNSIGNED_INT_8),
            (random_values(4 * VALUES_PER_BEAT), StreamType.UNSIGNED_INT_8),
            (random_values(4 * VALUES_PER_BEAT + 1), StreamType.UNSIGNED_INT_8),
        ])

    def test_mixed_types(self):
        """
        Back-to-back transfers switching between pass-through and both narrowings, including
        single-value transfers. Catches state leaking from one transfer into the next.
        """
        self.run_transfers([
            (random_values(5 * VALUES_PER_BEAT + 7), StreamType.UNSIGNED_INT_32),
            (random_values(1), StreamType.UNSIGNED_INT_16),
            (random_values(1), StreamType.UNSIGNED_INT_8),
            (random_values(2 * VALUES_PER_BEAT), StreamType.UNSIGNED_INT_16),
            (random_values(1), StreamType.UNSIGNED_INT_32),
            (random_values(3 * VALUES_PER_BEAT + 3), StreamType.UNSIGNED_INT_8),
            (random_values(VALUES_PER_BEAT + 3), StreamType.UNSIGNED_INT_16),
        ])
