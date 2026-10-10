package ${PACKAGE}.common;

import java.io.Serializable;
import java.util.List;

public record PageResult<T>(List<T> list, long total, long page, long size) implements Serializable {

    public static <T> PageResult<T> of(List<T> list, long total, long page, long size) {
        return new PageResult<>(list, total, page, size);
    }
}
