package ${PACKAGE}.module.example.controller;

import ${PACKAGE}.common.Result;
import ${PACKAGE}.module.example.dto.ExampleQueryDTO;
import ${PACKAGE}.module.example.service.ExampleService;
import ${PACKAGE}.module.example.vo.ExampleHelloVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 示例 Controller：首页靠 `/api/example/hello` 判断前后端是否连通。
 * 接手后整个 example 模块可以删掉（记得同步删掉 WebConfig 白名单里那一行与首页的调用）。
 */
@RestController
@RequestMapping("/api/example")
@RequiredArgsConstructor
public class ExampleController {

    private final ExampleService exampleService;

    @GetMapping("/hello")
    public Result<ExampleHelloVO> hello(@RequestParam(required = false) String name) {
        return Result.success(new ExampleHelloVO(exampleService.greeting(name), true));
    }

    @PostMapping("/echo")
    public Result<ExampleHelloVO> echo(@Valid @RequestBody ExampleQueryDTO body) {
        return Result.success(new ExampleHelloVO(exampleService.greeting(body.getName()), true));
    }
}
