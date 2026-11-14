// SPDX-License-Identifier: GPL-2.0-only
/* POCO F4 L11R 38:08:0a: stock 60/120 Hz commands, fixed rate selected at probe.
 * Provenance and remaining hardware assumptions: docs/pmos-display.md.
 */
#include <linux/backlight.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/property.h>
#include <linux/regulator/consumer.h>
#include <drm/display/drm_dsc.h>
#include <drm/drm_connector.h>
#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>

struct l11r_cmd {
 u8 type, channel, ack, delay_ms;
 u16 length;
 u8 payload[129];
};
#include "munch-l11r-init.h"
#include "munch-l11r-120.h"

struct l11r {
 struct drm_panel panel;
 struct mipi_dsi_device *dsi;
 struct regulator *vddio, *vci;
 struct gpio_desc *reset;
 struct drm_dsc_config dsc;
 unsigned int refresh_rate;
 bool prepared;
};

static struct l11r *to_l11r(struct drm_panel *p)
{
 return container_of(p, struct l11r, panel);
}

/* Keep stock packet types: vendor register writes are explicitly long DCS
 * packets, including those whose payload would fit a short packet. The host
 * is powered first via prepare_prev_first. No read or ACK is invented here.
 */
static int l11r_send(struct l11r *ctx, const struct l11r_cmd *cmds, size_t count)
{
 size_t i;
 for (i = 0; i < count; i++) {
  const struct l11r_cmd *cmd = &cmds[i];
  struct mipi_dsi_msg msg = {
   .channel = cmd->channel, .type = cmd->type,
   .flags = MIPI_DSI_MSG_USE_LPM | (cmd->ack ? MIPI_DSI_MSG_REQ_ACK : 0),
   .tx_len = cmd->length, .tx_buf = cmd->payload,
  };
  ssize_t ret = ctx->dsi->host->ops->transfer(ctx->dsi->host, &msg);
  if (ret < 0) {
   dev_err(&ctx->dsi->dev, "L11R packet %zu (type 0x%02x) failed: %zd\n", i, cmd->type, ret);
   return ret;
  }
  if (cmd->delay_ms)
   msleep(cmd->delay_ms);
 }
 return 0;
}

static int l11r_prepare(struct drm_panel *panel)
{
 struct l11r *ctx = to_l11r(panel);
 int ret;
 if (ctx->prepared)
  return 0;
 ret = regulator_enable(ctx->vddio);
 if (ret)
  return ret;
 ret = regulator_enable(ctx->vci);
 if (ret)
  goto disable_io;
 /* Stock physical reset: low 12 ms, high 10 ms. GPIO is active-low. */
 gpiod_set_value_cansleep(ctx->reset, 1);
 msleep(12);
 gpiod_set_value_cansleep(ctx->reset, 0);
 msleep(10);
 if (ctx->refresh_rate == 120)
  ret = l11r_send(ctx, l11r_on_120, ARRAY_SIZE(l11r_on_120));
 else
  ret = l11r_send(ctx, l11r_on, ARRAY_SIZE(l11r_on));
 if (ret)
  goto disable_vci;
 ctx->prepared = true;
 dev_info(&ctx->dsi->dev, "L11R stock %u Hz sequence sent\n", ctx->refresh_rate);
 return 0;
disable_vci:
 gpiod_set_value_cansleep(ctx->reset, 1);
 regulator_disable(ctx->vci);
disable_io:
 regulator_disable(ctx->vddio);
 return ret;
}

static int l11r_disable(struct drm_panel *panel)
{
 struct l11r *ctx = to_l11r(panel);
 if (!ctx->prepared)
  return 0;
 if (ctx->refresh_rate == 120)
  return l11r_send(ctx, l11r_off_120, ARRAY_SIZE(l11r_off_120));
 return l11r_send(ctx, l11r_off, ARRAY_SIZE(l11r_off));
}

static int l11r_unprepare(struct drm_panel *panel)
{
 struct l11r *ctx = to_l11r(panel);
 int ret, ret_io;
 if (!ctx->prepared)
  return 0;
 gpiod_set_value_cansleep(ctx->reset, 1);
 msleep(10);
 ret = regulator_disable(ctx->vci);
 ret_io = regulator_disable(ctx->vddio);
 ctx->prepared = false;
 return ret ? ret : ret_io;
}

static const struct drm_display_mode l11r_modes[] = { {
 .clock = (1080 + 16 + 8 + 8) * (2400 + 600 + 32 + 560) * 60 / 1000,
 .hdisplay = 1080, .hsync_start = 1080 + 16,
 .hsync_end = 1080 + 16 + 8, .htotal = 1080 + 16 + 8 + 8,
 .vdisplay = 2400, .vsync_start = 2400 + 600,
 .vsync_end = 2400 + 600 + 32, .vtotal = 2400 + 600 + 32 + 560,
 .type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED,
}, {
 .clock = (1080 + 16 + 8 + 8) * (2400 + 4 + 4 + 8) * 120 / 1000,
 .hdisplay = 1080, .hsync_start = 1080 + 16,
 .hsync_end = 1080 + 16 + 8, .htotal = 1080 + 16 + 8 + 8,
 .vdisplay = 2400, .vsync_start = 2400 + 4,
 .vsync_end = 2400 + 4 + 4, .vtotal = 2400 + 4 + 4 + 8,
 .type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED,
} };

static int l11r_get_modes(struct drm_panel *panel, struct drm_connector *connector)
{
 struct l11r *ctx = to_l11r(panel);
 struct drm_display_mode *mode = drm_mode_duplicate(connector->dev,
                       &l11r_modes[ctx->refresh_rate == 120]);
 if (!mode)
  return -ENOMEM;
 drm_mode_set_name(mode);
 drm_mode_probed_add(connector, mode);
 /* Stock physical dimensions are 695 x 1546 units of 0.1 mm. */
 connector->display_info.width_mm = 70;
 connector->display_info.height_mm = 155;
 connector->display_info.bpc = 8;
 return 1;
}

static const struct drm_panel_funcs l11r_funcs = {
 .prepare = l11r_prepare, .disable = l11r_disable,
 .unprepare = l11r_unprepare, .get_modes = l11r_get_modes,
};

static int l11r_backlight_update(struct backlight_device *bl)
{
 struct l11r *ctx = bl_get_data(bl);
 if (!ctx->prepared)
  return 0;
 {
  unsigned long flags = ctx->dsi->mode_flags;
  int ret;
  ctx->dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;
  ret = mipi_dsi_dcs_set_display_brightness_large(ctx->dsi, backlight_get_brightness(bl));
  ctx->dsi->mode_flags = flags;
  return ret;
 }
}

static const struct backlight_ops l11r_backlight_ops = {
 .update_status = l11r_backlight_update,
};

static int l11r_probe(struct mipi_dsi_device *dsi)
{
 struct device *dev = &dsi->dev;
 const struct backlight_properties props = {
  .type = BACKLIGHT_RAW, .brightness = 536, .max_brightness = 2047,
 };
 struct l11r *ctx;
 int ret;
 if (!dsi->host->ops->transfer)
  return -EOPNOTSUPP;
 ctx = devm_drm_panel_alloc(dev, struct l11r, panel,
                            &l11r_funcs, DRM_MODE_CONNECTOR_DSI);
 if (IS_ERR(ctx))
  return PTR_ERR(ctx);
 ctx->dsi = dsi;
 ctx->refresh_rate = 60;
 if (device_property_present(dev, "xiaomi,refresh-rate")) {
  ret = device_property_read_u32(dev, "xiaomi,refresh-rate", &ctx->refresh_rate);
  if (ret)
   return dev_err_probe(dev, ret, "refresh rate\n");
 }
 if (ctx->refresh_rate != 60 && ctx->refresh_rate != 120)
  return dev_err_probe(dev, -EINVAL, "unsupported refresh rate\n");
 ctx->vddio = devm_regulator_get(dev, "vddio");
 if (IS_ERR(ctx->vddio))
  return dev_err_probe(dev, PTR_ERR(ctx->vddio), "vddio supply\n");
 ctx->vci = devm_regulator_get(dev, "vci");
 if (IS_ERR(ctx->vci))
  return dev_err_probe(dev, PTR_ERR(ctx->vci), "vci supply\n");
 ctx->reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
 if (IS_ERR(ctx->reset))
  return dev_err_probe(dev, PTR_ERR(ctx->reset), "reset GPIO\n");
 ctx->dsc = (struct drm_dsc_config) {
  .dsc_version_major = 1, .dsc_version_minor = 1,
  .slice_width = 540, .slice_height = 8, .slice_count = 2,
  .bits_per_component = 8, .bits_per_pixel = 8 << 4,
  .block_pred_enable = true,
 };
 dsi->lanes = 4;
 dsi->format = MIPI_DSI_FMT_RGB888;
 dsi->mode_flags = MIPI_DSI_MODE_LPM | MIPI_DSI_CLOCK_NON_CONTINUOUS;
 dsi->dsc = &ctx->dsc;
 mipi_dsi_set_drvdata(dsi, ctx);
 ctx->panel.prepare_prev_first = true;
 ctx->panel.backlight = devm_backlight_device_register(dev, "munch-l11r", dev,
                 ctx, &l11r_backlight_ops, &props);
 if (IS_ERR(ctx->panel.backlight))
  return dev_err_probe(dev, PTR_ERR(ctx->panel.backlight), "backlight\n");
 drm_panel_add(&ctx->panel);
 ret = mipi_dsi_attach(dsi);
 if (ret) {
  drm_panel_remove(&ctx->panel);
  return dev_err_probe(dev, ret, "DSI attach\n");
 }
 dev_info(dev, "L11R 38:08:0a attached (1080x2400, %u Hz, DSC)\n", ctx->refresh_rate);
 return 0;
}

static void l11r_remove(struct mipi_dsi_device *dsi)
{
 struct l11r *ctx = mipi_dsi_get_drvdata(dsi);
 mipi_dsi_detach(dsi);
 drm_panel_remove(&ctx->panel);
}

static void l11r_shutdown(struct mipi_dsi_device *dsi)
{
 struct l11r *ctx = mipi_dsi_get_drvdata(dsi);
 drm_panel_disable(&ctx->panel);
 drm_panel_unprepare(&ctx->panel);
}

static const struct of_device_id l11r_match[] = {
 { .compatible = "xiaomi,munch-l11r-38080a" }, { }
};
MODULE_DEVICE_TABLE(of, l11r_match);
static struct mipi_dsi_driver l11r_driver = {
 .probe = l11r_probe, .remove = l11r_remove, .shutdown = l11r_shutdown,
 .driver = { .name = "panel-xiaomi-munch-l11r", .of_match_table = l11r_match },
};
module_mipi_dsi_driver(l11r_driver);
MODULE_DESCRIPTION("POCO F4 L11R 38:08:0a DSC panel experiment");
MODULE_LICENSE("GPL");
