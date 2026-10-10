package ${PACKAGE}.module.example.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ExampleQueryDTO {

    @NotBlank(message = "不能为空")
    private String name;
}
