// SPDX-License-Identifier: GPL-2.0-only
/* Xiaomi POCO F4 touch bring-up. Protocol derived from Xiaomi munch-s-oss,
 * focaltech_spi, copyright 2012-2020 FocalTech Systems, Ltd.
 * No bootloader, flash erase, firmware upgrade or factory-test commands.
 */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/input/mt.h>
#include <linux/input/touchscreen.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <linux/spi/spi.h>
#include "munch-touch-protocol.h"

struct munch_touch {
 struct spi_device *spi;
 struct input_dev *input;
 struct gpio_desc *reset;
 struct regulator *vio, *vdd;
 struct touchscreen_properties prop;
 u8 tx[MUNCH_TOUCH_BYTES + 9];
 u8 rx[MUNCH_TOUCH_BYTES + 9];
};

static int munch_touch_read(struct munch_touch *ts, u8 reg, u8 *data, size_t n)
{
 size_t len = n + 9;
 int retry, ret = -EIO;
 if (!n || n > MUNCH_TOUCH_BYTES)
  return -EINVAL;
 for (retry = 0; retry < 3; retry++) {
  struct spi_transfer xfer = { .tx_buf = ts->tx, .rx_buf = ts->rx, .len = len };
  memset(ts->tx, 0, sizeof(ts->tx));
  memset(ts->rx, 0, sizeof(ts->rx));
  ts->tx[0] = reg;
  ts->tx[1] = 0xa0; /* read + CRC */
  ts->tx[2] = n >> 8;
  ts->tx[3] = n;
  ret = spi_sync_transfer(ts->spi, &xfer, 1);
  usleep_range(150, 250);
  if (ret)
   continue;
  if ((ts->rx[3] & 0xa0) ||
      munch_touch_crc(ts->rx + 7, n) != (ts->rx[7 + n] | (ts->rx[8 + n] << 8))) {
   ret = -EIO;
   continue;
  }
  memcpy(data, ts->rx + 7, n);
  return 0;
 }
 return ret;
}

static irqreturn_t munch_touch_irq(int irq, void *data)
{
 struct munch_touch *ts = data;
 struct munch_touch_point points[MUNCH_TOUCH_POINTS];
 u8 packet[MUNCH_TOUCH_BYTES];
 int n, i, ret;
 ret = munch_touch_read(ts, 1, packet, sizeof(packet));
 if (ret) {
  dev_err_ratelimited(&ts->spi->dev, "touch SPI/CRC read failed: %d\n", ret);
  return IRQ_HANDLED;
 }
 n = munch_touch_decode(packet, points, ts->prop.max_x, ts->prop.max_y);
 if (n < 0) {
  dev_warn_ratelimited(&ts->spi->dev, "invalid touch frame: header %02x %02x\n", packet[0], packet[1]);
  return IRQ_HANDLED;
 }
 for (i = 0; i < n; i++) {
  input_mt_slot(ts->input, points[i].id);
  input_mt_report_slot_state(ts->input, MT_TOOL_FINGER, true);
  touchscreen_report_pos(ts->input, &ts->prop, points[i].x, points[i].y, true);
  input_report_abs(ts->input, ABS_MT_TOUCH_MAJOR, points[i].area ?: 1);
 }
 input_mt_sync_frame(ts->input);
 input_sync(ts->input);
 return IRQ_HANDLED;
}

static void munch_touch_power_off(void *data)
{
 struct munch_touch *ts = data;
 gpiod_set_value_cansleep(ts->reset, 1);
 regulator_disable(ts->vdd);
 regulator_disable(ts->vio);
}

static int munch_touch_probe(struct spi_device *spi)
{
 struct device *dev = &spi->dev;
 struct munch_touch *ts;
 u8 high = 0, low = 0;
 int ret, attempt;
 if (spi->irq <= 0)
  return dev_err_probe(dev, -EINVAL, "missing touch IRQ\n");
 ts = devm_kzalloc(dev, sizeof(*ts), GFP_KERNEL);
 if (!ts)
  return -ENOMEM;
 ts->spi = spi;
 spi_set_drvdata(spi, ts);
 spi->mode = SPI_MODE_0;
 spi->bits_per_word = 8;
 ret = spi_setup(spi);
 if (ret)
  return ret;
 ts->vio = devm_regulator_get(dev, "vio");
 if (IS_ERR(ts->vio))
  return dev_err_probe(dev, PTR_ERR(ts->vio), "vio\n");
 ts->vdd = devm_regulator_get(dev, "vdd");
 if (IS_ERR(ts->vdd))
  return dev_err_probe(dev, PTR_ERR(ts->vdd), "vdd\n");
 ts->reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
 if (IS_ERR(ts->reset))
  return dev_err_probe(dev, PTR_ERR(ts->reset), "reset\n");
 msleep(1);
 ret = regulator_enable(ts->vio);
 if (ret)
  return ret;
 msleep(1);
 ret = regulator_enable(ts->vdd);
 if (ret) {
  regulator_disable(ts->vio);
  return ret;
 }
 ret = devm_add_action_or_reset(dev, munch_touch_power_off, ts);
 if (ret)
  return ret;
 msleep(10);
 gpiod_set_value_cansleep(ts->reset, 0);
 msleep(200);
 /* Stock app ID 56:52. Do not enter ROM or accept another protocol blindly. */
 for (attempt = 0; attempt < 10; attempt++) {
  ret = munch_touch_read(ts, 0xa3, &high, 1);
  if (!ret)
   ret = munch_touch_read(ts, 0x9f, &low, 1);
  if (!ret && high == 0x56 && low == 0x52)
   break;
  msleep(100);
 }
 if (ret || high != 0x56 || low != 0x52)
  return dev_err_probe(dev, ret ?: -ENODEV,
                       "touch app ID %02x:%02x, expected 56:52; no firmware writes attempted\n", high, low);
 ts->input = devm_input_allocate_device(dev);
 if (!ts->input)
  return -ENOMEM;
 ts->input->name = "POCO F4 FT3658U Touchscreen";
 ts->input->id.bustype = BUS_SPI;
 input_set_abs_params(ts->input, ABS_MT_POSITION_X, 0, 10799, 0, 0);
 input_set_abs_params(ts->input, ABS_MT_POSITION_Y, 0, 23999, 0, 0);
 input_set_abs_params(ts->input, ABS_MT_TOUCH_MAJOR, 0, 15, 0, 0);
 touchscreen_parse_properties(ts->input, true, &ts->prop);
 ret = input_mt_init_slots(ts->input, MUNCH_TOUCH_POINTS,
                           INPUT_MT_DIRECT | INPUT_MT_DROP_UNUSED);
 if (ret)
  return ret;
 ret = input_register_device(ts->input);
 if (ret)
  return ret;
 ret = devm_request_threaded_irq(dev, spi->irq, NULL, munch_touch_irq,
                                 IRQF_ONESHOT, dev_name(dev), ts);
 if (ret)
  return dev_err_probe(dev, ret, "touch IRQ\n");
 dev_info(dev, "FT3658U app 56:52 ready, raw coordinates %ux%u, IRQ %d\n",
          ts->prop.max_x + 1, ts->prop.max_y + 1, spi->irq);
 return 0;
}
static const struct of_device_id munch_touch_match[] = {
 { .compatible = "xiaomi,munch-ft3658u" }, { }
};
MODULE_DEVICE_TABLE(of, munch_touch_match);
static const struct spi_device_id munch_touch_ids[] = {
 { "munch-ft3658u", 0 }, { }
};
MODULE_DEVICE_TABLE(spi, munch_touch_ids);
static struct spi_driver munch_touch_driver = {
 .driver = { .name = "munch-ft3658u", .of_match_table = munch_touch_match },
 .probe = munch_touch_probe,
 .id_table = munch_touch_ids,
};
module_spi_driver(munch_touch_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("POCO F4 FT3658U SPI touch experiment");
