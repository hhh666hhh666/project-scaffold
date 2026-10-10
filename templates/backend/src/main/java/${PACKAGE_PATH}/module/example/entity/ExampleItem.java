package ${PACKAGE}.module.example.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 示例实体：照它的样子写你自己的实体。表名与字段的真相源是迁移脚本。
 */
@Data
@TableName("example_item")
public class ExampleItem {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    private LocalDateTime createTime;
}
