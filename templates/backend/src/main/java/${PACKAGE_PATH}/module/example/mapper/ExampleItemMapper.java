package ${PACKAGE}.module.example.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import ${PACKAGE}.module.example.entity.ExampleItem;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ExampleItemMapper extends BaseMapper<ExampleItem> {
}
