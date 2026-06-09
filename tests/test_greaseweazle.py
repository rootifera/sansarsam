from pathlib import Path
import unittest

from services.greaseweazle import (
    InvalidExtraFlagsError,
    build_clean_command,
    build_convert_command,
    build_erase_command,
    build_read_command,
    build_update_command,
    build_write_command,
)


class GreaseweazleCommandTests(unittest.TestCase):
    def test_write_command_parses_quoted_extra_flags(self) -> None:
        command = build_write_command(
            image_path=Path("/tmp/My Disk.img"),
            fmt="ibm.1440",
            verify=True,
            extra_flags='--drive "unit 0" --tracks=c=0-79',
            gw_executable="gw",
        )

        self.assertEqual(
            command,
            [
                "gw",
                "write",
                "--format",
                "ibm.1440",
                "--drive",
                "unit 0",
                "--tracks=c=0-79",
                "/tmp/My Disk.img",
            ],
        )

    def test_write_command_adds_no_verify_when_requested(self) -> None:
        command = build_write_command(
            image_path=Path("disk.img"),
            fmt="",
            verify=False,
            extra_flags="",
            gw_executable="gw",
        )

        self.assertEqual(command, ["gw", "write", "--no-verify", "disk.img"])

    def test_read_command_only_adds_format_for_img_outputs(self) -> None:
        img_command = build_read_command(
            output_path=Path("disk.img"),
            output_type="IMG",
            fmt="ibm.1440",
            extra_flags="",
            gw_executable="gw",
        )
        scp_command = build_read_command(
            output_path=Path("disk.scp"),
            output_type="SCP",
            fmt="ibm.1440",
            extra_flags="",
            gw_executable="gw",
        )

        self.assertEqual(img_command, ["gw", "read", "--format", "ibm.1440", "disk.img"])
        self.assertEqual(scp_command, ["gw", "read", "disk.scp"])

    def test_convert_command_rejects_malformed_extra_flags(self) -> None:
        with self.assertRaises(InvalidExtraFlagsError):
            build_convert_command(
                input_path=Path("source.scp"),
                output_path=Path("target.img"),
                fmt="ibm.1440",
                no_clobber=True,
                extra_flags='--name "unterminated',
                gw_executable="gw",
            )

    def test_erase_command_accepts_format_and_extra_flags(self) -> None:
        command = build_erase_command(
            fmt="ibm.1440",
            extra_flags='--drive "unit 0"',
            gw_executable="gw",
        )

        self.assertEqual(command, ["gw", "erase", "--format", "ibm.1440", "--drive", "unit 0"])

    def test_clean_command_accepts_extra_flags(self) -> None:
        command = build_clean_command(
            extra_flags="--drive B",
            gw_executable="gw",
        )

        self.assertEqual(command, ["gw", "clean", "--drive", "B"])

    def test_update_command_accepts_extra_flags(self) -> None:
        command = build_update_command(
            extra_flags="v1.22",
            gw_executable="gw",
        )

        self.assertEqual(command, ["gw", "update", "v1.22"])


if __name__ == "__main__":
    unittest.main()
