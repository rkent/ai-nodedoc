# republish

*This file is ai generated and may contain mistakes. If you edit this file, remove this notice to prevent rewriting by ai.*

## Description

The `republish` node (class `point_cloud_transport::Republisher`) subscribes to a point cloud topic using a selectable input transport and republishes the decoded `sensor_msgs/PointCloud2` messages using either all available output transports or a single specified output transport. It is useful for converting between different point cloud transport encodings on-the-fly.

## Subscribers

| Topic | Type | Description |
|-------|------|-------------|
| `in` | `sensor_msgs/msg/PointCloud2` | Incoming point cloud stream, received using the transport specified by `in_transport` |

## Publishers

| Topic | Type | Description |
|-------|------|-------------|
| `out` | `sensor_msgs/msg/PointCloud2` | Republished point cloud stream, published using the transport(s) specified by `out_transport` (or all transports if not set) |

## Parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `in_transport` | `string` | `"raw"` | Transport type to use when subscribing to the input topic (e.g. `raw`, `draco`, `zlib`) |
| `out_transport` | `string` | `""` | Transport type to use for output. If empty, all available transports are advertised |

## Example Usage

```bash
ros2 run point_cloud_transport republish --ros-args -p in_transport:=raw -p out_transport:=draco --remap in:=/input/points --remap out:=/output/points
```
